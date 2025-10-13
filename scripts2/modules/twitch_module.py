import asyncio
import datetime
from twitchAPI.twitch import Twitch
from twitchAPI.type import AuthScope, ChatEvent
from twitchAPI.chat import Chat, ChatMessage, EventData
from twitchAPI.oauth import UserAuthenticator, refresh_access_token
from twitchAPI.eventsub.websocket import EventSubWebsocket
from twitchAPI.object.eventsub import ChannelFollowEvent

from scripts2.modules.base_module import BaseModule
from scripts2.utils.filter_utils import contains_banned_words
from scripts2.utils.log_utils import get_logger
from scripts2.config.config import STREAMER_SCOPES, BOT_SCOPES, BLACKLISTED_WORDS_LIST, WHITELISTED_WORDS_LIST

"""
Module for integrating with Twitch API, handling authentication, chat monitoring, and token refresh.

This module provides functionality to connect to Twitch, authenticate bot and streamer accounts,
monitor chat messages, filter inappropriate content, and publish events to the central event broker.
It also manages token refresh to maintain authenticated sessions.
"""

class TwitchModule(BaseModule):
    """
    Twitch integration module for handling Twitch API connections and chat interactions.

    This class manages authentication for bot and streamer accounts, sets up chat monitoring,
    filters chat messages for banned words, and integrates with the application's event broker
    and memory management systems. It supports periodic token refresh to maintain connections.

    Attributes:
        settings: Configuration settings object containing Twitch credentials and channel info.
        signals: Signal handlers for the module.
        twitch_enabled: Boolean flag to enable/disable overall Twitch functionality.
        chat_enabled: Boolean flag to enable/disable chat message monitoring.
        event_broker: Central event broker instance for publishing chat messages.
        twitch_bot: Twitch API client instance for bot account operations.
        twitch_streamer: Twitch API client instance for streamer account operations.
        chat: Chat monitoring instance for real-time message processing.
        memory_manager: Memory manager instance for queuing and storing user messages.
    """

    def __init__(self, settings, signals, event_broker, memory_manager, twitch_enabled=True, chat_enabled=True):
        """
        Initialize the TwitchModule with necessary dependencies and settings.

        Args:
            settings: Configuration object containing Twitch client ID, secret, channel, and tokens.
            signals: Signal handlers for module lifecycle events.
            event_broker: Event broker for publishing Twitch chat messages to other modules.
            memory_manager: Memory manager for storing filtered chat messages.
            twitch_enabled: Whether to enable Twitch integration (default True).
            chat_enabled: Whether to enable chat message ingestion (default True).
        """
        super().__init__(name="TwitchModule")
        self.settings = settings
        self.signals = signals
        self.twitch_enabled = twitch_enabled
        self.chat_enabled = chat_enabled
        self.event_broker = event_broker 
        self.memory_manager = memory_manager

        self.twitch_bot = None
        self.twitch_streamer = None
        self.chat = None
        self.eventsub = None

    async def start(self):
        """
        Start the TwitchModule if Twitch integration is enabled.

        Checks the twitch_enabled flag and proceeds with starting the module.
        Calls the parent class start method if enabled.

        Returns:
            None
        """
        if not self.twitch_enabled:
            self.logger.info(f"[start] {self.name} is disabled. Not starting.")
            return
        await super().start()

    async def run(self):
        """
        Main run loop for the TwitchModule.

        Starts the Twitch client, and if successful, enters a loop that refreshes
        authentication tokens every hour. Runs until the module is stopped.

        Returns:
            None
        """
        await super().run()
        self.connected = await self._start_client()

        if not self.connected:
            self.logger.error("Failed to connect Twitch client. Exiting TwitchModule.")
            self._running = False
            await self.stop()
            return

        self.eventsub = EventSubWebsocket(self.twitch_streamer)
        self.eventsub.start()

        await self._subscribe_to_follow_events()
        
        while self._running:
            self.logger.info("[run] Twitch module is running...")
            await self._refresh_tokens()
            await asyncio.sleep(60 * 60)

    async def disconnect(self):
        """
        Disconnect from Twitch services.

        Stops the chat monitoring, closes bot and streamer Twitch clients,
        and updates the connection status.

        Returns:
            None
        """
        self.logger.info("[disconnect] Disconnecting TwitchClient...")
        if self.chat and self.chat_enabled:
            self.chat.stop()
        if self.twitch_bot:
            await self.twitch_bot.close()
        if self.twitch_streamer:
            await self.twitch_streamer.close()
        if self.eventsub:
            await self.eventsub.stop()
        self.connected = False
        self.logger.info("[disconnect] Disconnected successfully.")

    async def stop(self):
        """
        Stop the TwitchModule.

        Calls disconnect to clean up connections and then calls the parent stop method.

        Returns:
            None
        """
        await self.disconnect()
        await super().stop()

    async def _start_client(self) -> bool:
        """
        Initialize and start the Twitch client connections.

        Authenticates bot and streamer accounts, sets up chat if enabled,
        and joins the specified Twitch channel.

        Returns:
            bool: True if connection successful, False otherwise.

        Raises:
            Exception: If authentication or connection fails.
        """
        self.logger.info("[start] Starting TwitchClient...")
        try:
            await self._authenticate_bot_account()
            await self._authenticate_streamer_account()
            if self.chat_enabled:
                await self._setup_chat()
            else:
                self.logger.info("[_start_client] Twitch chat ingestion currently disabled")
            self.logger.info(f"[start] Connected to Twitch channel: {self.settings.twitch_channel}")
            return True
        except Exception as e:
            self.logger.error(f"[start] Failed to connect TwitchClient: {e}")
            return False

    async def _authenticate_bot_account(self):
        """
        Authenticate the bot account with Twitch API.

        Creates a Twitch client for the bot, checks for existing tokens,
        and performs interactive authentication if needed.

        Returns:
            None

        Raises:
            Exception: If authentication fails.
        """
        self.twitch_bot = await Twitch(self.settings.twitch_client_id, self.settings.twitch_client_secret)

        if not self.settings.bot_oauth_token or not self.settings.bot_refresh_token:
            self.logger.info("[_authenticate_bot_account] No bot OAuth token found, authenticating interactively...")
            auth = UserAuthenticator(self.twitch_bot, BOT_SCOPES, url=self.settings.twitch_redirect_uri)
            token, refresh_token = await auth.authenticate()
            self.settings.bot_oauth_token = token
            self.settings.bot_refresh_token = refresh_token
        else:
            await self.twitch_bot.set_user_authentication(
                self.settings.bot_oauth_token,
                BOT_SCOPES,
                self.settings.bot_refresh_token
            )

    async def _authenticate_streamer_account(self):
        """
        Authenticate the streamer account with Twitch API.

        Creates a Twitch client for the streamer, checks for existing tokens,
        and performs interactive authentication if needed.

        Returns:
            None

        Raises:
            Exception: If authentication fails.
        """
        self.twitch_streamer = await Twitch(self.settings.twitch_client_id, self.settings.twitch_client_secret)

        if not self.settings.streamer_oauth_token or not self.settings.streamer_refresh_token:
            self.logger.info("[_authenticate_streamer_account] No streamer OAuth token found, authenticating interactively...")
            auth = UserAuthenticator(self.twitch_streamer, STREAMER_SCOPES, url=self.settings.twitch_redirect_uri)
            token, refresh_token = await auth.authenticate()
            self.settings.streamer_oauth_token = token
            self.settings.streamer_refresh_token = refresh_token
        else:
            await self.twitch_streamer.set_user_authentication(
                self.settings.streamer_oauth_token,
                STREAMER_SCOPES,
                self.settings.streamer_refresh_token
            )

    async def _setup_chat(self):
        """
        Set up chat monitoring for the Twitch channel.

        Creates a Chat instance, registers event handlers for ready and message events,
        and starts the chat monitoring.

        Returns:
            None
        """
        self.chat = await Chat(self.twitch_bot)
        self.chat.register_event(ChatEvent.READY, self._on_ready)
        self.chat.register_event(ChatEvent.MESSAGE, self._on_message)
        self.chat.register_event(ChatEvent.SUB, self._on_subscription)
        self.chat.register_event(ChatEvent.RAID, self._on_raid)
        self.chat.start()

    async def _on_ready(self, event: EventData):
        """
        Event handler called when the chat bot is ready.

        Joins the specified Twitch channel upon readiness.

        Args:
            event: EventData containing chat event information.

        Returns:
            None

        Raises:
            Exception: If joining the channel fails.
        """
        try:
            self.logger.info("[_on_ready] Bot ready, joining channel...")
            await event.chat.join_room(self.settings.twitch_channel)
            self.logger.info(f"[_on_ready] Joined channel: {self.settings.twitch_channel}")
        except Exception as e:
            self.logger.error(f"[_on_ready] Failed to join channel: {e}")

    async def _on_message(self, msg: ChatMessage):
        """
        Event handler for incoming chat messages.

        Processes chat messages, publishes them to the event broker,
        and queues filtered messages to memory if they pass content filters.

        Args:
            msg: ChatMessage object containing message details.

        Returns:
            None

        Raises:
            Exception: If message processing fails.
        """
        try:
            user = msg.user.name
            message = msg.text.strip()

            self.logger.debug(f"[_on_message] Message from {user}: {message}")

            if contains_banned_words(message, blacklist=BLACKLISTED_WORDS_LIST, 
                                     whitelist=WHITELISTED_WORDS_LIST):
                return
            
            if contains_banned_words(user, blacklist=BLACKLISTED_WORDS_LIST, 
                                     whitelist=WHITELISTED_WORDS_LIST):
                user = "Someone"

            self.event_broker.publish_event({
                "type": "twitch_chat",
                "user": user,
                "text": message,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
            })

            self.memory_manager.queue_user_message(
                content=message,
                user_id=user,
                metadata={"type": "twitch_chat"}
            )

            self.logger.info("[_on_message] Chat message published to broker")

        except Exception as e:
            self.logger.error(f"[_on_message] Error handling message: {e}")

    async def _on_subscription(self, event: EventData):
        try:
            self.logger.debug(f"Sub System Message {event.system_message}")
            self.logger.debug(f"Sub Plan Name {event.sub_plan_name}")
            self.logger.debug(f"Sub Type {event.sub_type}")           
            self.logger.debug(f"Sub Message{event.sub_message}")       

            user = "Someone"
            tier = event.sub_plan_name
            sub_msg = event.sub_message
            sub_type = event.sub_type

            if contains_banned_words(user, blacklist=BLACKLISTED_WORDS_LIST, 
                                     whitelist=WHITELISTED_WORDS_LIST):
                user = "Someone"    
            
            if sub_type == "resub":
                message = f"{user} just resubscribed with {tier}!"
            elif sub_type == "gift":
                message = f"{user} just gifted a {tier} subscription!"
            elif sub_type == "prime":
                message = f"{user} just subscribed with Prime Gaming!"
            else:
                message = f"{user} just subscribed with {tier}!"

            if sub_msg:
                message += f" They said: {sub_msg}"

            self.logger.info(f"Subscription event: {message}")

            self.event_broker.publish_event({
                "type": "twitch_subscription",
                "user": user,
                "tier": tier,
                "text": message,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
            })

            self.memory_manager.queue_user_message(
                content=message,
                user_id=user,
                metadata={"type": "twitch_subscription", "tier": tier}
            )
        except Exception as e:
            self.logger.error(f"[_on_subscription] Error handling subscription event: {e}")

    async def _on_raid(self, event: EventData):
        try:
            raider = event.raid_raider
            viewers = event.raid_viewers
            message = f"{raider} is raiding with {viewers} viewers!"

            self.logger.info(f"Raid event: {message}")

            if contains_banned_words(user, blacklist=BLACKLISTED_WORDS_LIST, 
                                     whitelist=WHITELISTED_WORDS_LIST):
                user = "Someone"

            self.event_broker.publish_event({
                "type": "twitch_raid",
                "user": raider,
                "viewers": viewers,
                "text": message,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
            })

            self.memory_manager.queue_user_message(
                content=message,
                user_id=raider,
                metadata={"type": "twitch_raid", "viewers": viewers}
            )
        except Exception as e:
            self.logger.error(f"[_on_raid] Error handling raid event: {e}")

    async def _on_follow(self, event: ChannelFollowEvent):
        try:
            user = event.event.user_name
            broadcaster = event.event.broadcaster_user_name
            followed_at = event.event.followed_at

            message = f"{user} just followed the channel at {followed_at}!"

            self.logger.info(f"Follow event: {message}")

            if contains_banned_words(user, blacklist=BLACKLISTED_WORDS_LIST, 
                                     whitelist=WHITELISTED_WORDS_LIST):
                user = "Someone"

            self.event_broker.publish_event({
                "type": "twitch_follow",
                "user": user,
                "followed_at": followed_at,
                "text": message,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
            })

            self.memory_manager.queue_user_message(
                content=message,
                user_id=user,
                metadata={"type": "twitch_follow"}
            )
        except Exception as e:
            self.logger.error(f"[_on_follow] Error handling follow event: {e}")

    async def _subscribe_to_follow_events(self):
        try:
            self.logger.info("[_subscribe_to_follow_events] Subscribing to follow events...")

            try:
                users = []
                async for user in self.twitch_streamer.get_users(logins=[self.settings.twitch_channel]):
                    users.append(user)

            except Exception as e:
                self.logger.error(f"Error fetching users: {e}")
                return

            if not users:
                self.logger.error("No users found for given login")
                return

            user = users[0]
            broadcaster_id = user.id
            self.logger.info(f"Got broadcaster_id: {broadcaster_id}")

            method = self.eventsub.listen_channel_follow_v2
            self.logger.info(f"listen_channel_follow_v2 method: {method!r}")

            res = method(
                broadcaster_user_id=broadcaster_id,
                moderator_user_id=broadcaster_id,
                callback=self._on_follow
            )
            self.logger.info(f"Result of calling listen_channel_follow_v2: {res!r}")

            sub_id = await res
            self.logger.info(f"[_subscribe_to_follow_events] Follow subscription succeeded, id: {sub_id}")

        except Exception as e:
            self.logger.error(f"_subscribe_to_follow_events error: {e}")


    async def _refresh_tokens(self):
        """
        Refresh authentication tokens for bot and streamer accounts.

        Uses refresh tokens to obtain new access tokens and updates settings.
        Saves the updated tokens to persistent storage.

        Returns:
            None

        Raises:
            Exception: If token refresh fails.
        """
        try:
            self.logger.info("[_refresh_tokens] Refreshing tokens...")

            if self.settings.bot_refresh_token:
                new_token, new_refresh = await refresh_access_token(
                    self.settings.bot_refresh_token,
                    self.settings.twitch_client_id,
                    self.settings.twitch_client_secret
                )
                self.settings.bot_oauth_token = new_token
                self.settings.bot_refresh_token = new_refresh
                self.logger.info("[_refresh_tokens] Bot tokens refreshed")

            if self.settings.streamer_refresh_token:
                new_token, new_refresh = await refresh_access_token(
                    self.settings.streamer_refresh_token,
                    self.settings.twitch_client_id,
                    self.settings.twitch_client_secret
                )
                self.settings.streamer_oauth_token = new_token
                self.settings.streamer_refresh_token = new_refresh
                self.logger.info("[_refresh_tokens] Streamer tokens refreshed")

            self.settings.save()
        except Exception as e:
            self.logger.error(f"[_refresh_tokens] Error refreshing tokens: {e}")