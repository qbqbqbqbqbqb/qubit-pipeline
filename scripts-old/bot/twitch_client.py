"""
Direct Twitch API client using twitchAPI library.
Replaces twitchio-based implementation for more direct API control.
"""

import asyncio
import os
from typing import Optional, Dict, Any, List
from datetime import datetime

from twitchAPI.twitch import Twitch
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.type import AuthScope, ChatEvent
from twitchAPI.chat import Chat, EventData, ChatMessage, ChatSub, ChatCommand
from dotenv import load_dotenv

from scripts.utils.log_utils import get_logger
from scripts.config.config_manager import ConfigManager

logger = get_logger("TwitchClient")


class TwitchClient:
    """
    Direct Twitch API client using twitchAPI library.

    This client provides more direct control over Twitch integration compared to twitchio,
    handling chat messages, commands, and EventSub events through the official Twitch API.
    """

    def __init__(self, config: ConfigManager, message_handler=None, event_handler=None):
        """
        Initialize the Twitch client with dual-account support.

        Args:
            config: Configuration manager instance
            message_handler: Callback for handling chat messages (author, content, timestamp)
            event_handler: Callback for handling EventSub events
        """
        self.config = config
        self.message_handler = message_handler
        self.event_handler = event_handler

        self.twitch_bot: Optional[Twitch] = None  # For bot account (chat)
        self.twitch_streamer: Optional[Twitch] = None  # For streamer account (events)
        self.chat: Optional[Chat] = None
        self.authenticator_bot = None
        self.authenticator_streamer = None

        self.connected = False
        self.channel_name = None

        load_dotenv()
        self.app_id = os.getenv("TWITCH_CLIENT_ID")
        self.app_secret = os.getenv("TWITCH_CLIENT_SECRET")

        self.bot_oauth_token = os.getenv("BOT_OAUTH_TOKEN") or os.getenv("TWITCH_OAUTH_TOKEN")
        self.bot_refresh_token = os.getenv("BOT_REFRESH_TOKEN") or os.getenv("TWITCH_REFRESH_TOKEN")

        self.streamer_oauth_token = os.getenv("STREAMER_OAUTH_TOKEN")
        self.streamer_refresh_token = os.getenv("STREAMER_REFRESH_TOKEN")

        self.channel_name = os.getenv("TWITCH_CHANNEL")
        self.redirect_uri = os.getenv("TWITCH_REDIRECT_URI", "http://localhost")

        if not all([self.app_id, self.app_secret, self.bot_oauth_token, self.channel_name]):
            raise ValueError("Missing required Twitch API credentials. Need TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET, and BOT_OAUTH_TOKEN")

        self.bot_scopes = [
            AuthScope.CHAT_READ,
            AuthScope.CHAT_EDIT
        ]

        self.streamer_scopes = [
            AuthScope.CHANNEL_READ_SUBSCRIPTIONS,
            AuthScope.CHANNEL_MANAGE_RAIDS
        ]

    async def connect(self) -> bool:
        """
        Establish connection to Twitch API with dual-account authentication.

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            logger.info("[TwitchClient] Initializing dual-account Twitch API connection...")

            # === Authenticate Bot Account (for chat operations) ===
            logger.info("[TwitchClient] Authenticating bot account...")
            self.twitch_bot = await Twitch(self.app_id, self.app_secret)

            if self.bot_oauth_token and self.bot_refresh_token:
                try:
                    await self.twitch_bot.set_user_authentication(self.bot_oauth_token, self.bot_scopes, self.bot_refresh_token)
                    users = []
                    async for user in self.twitch_bot.get_users():
                        users.append(user)
                        break
                    if users:
                        logger.info("[TwitchClient] Bot account authenticated successfully")
                    else:
                        raise Exception("Bot token validation failed")
                except Exception as e:
                    logger.warning(f"[TwitchClient] Bot tokens failed ({str(e)}), attempting OAuth...")
                    self.authenticator_bot = UserAuthenticator(self.twitch_bot, self.bot_scopes, url=self.redirect_uri)
                    token, refresh_token = await self.authenticator_bot.authenticate()
                    await self.twitch_bot.set_user_authentication(token, self.bot_scopes, refresh_token)
                    logger.info("[TwitchClient] Bot OAuth authentication completed")
            else:
                logger.info("[TwitchClient] No bot tokens found, using OAuth flow...")
                self.authenticator_bot = UserAuthenticator(self.twitch_bot, self.bot_scopes, url=self.redirect_uri)
                token, refresh_token = await self.authenticator_bot.authenticate()
                await self.twitch_bot.set_user_authentication(token, self.bot_scopes, refresh_token)

            # === Authenticate Streamer Account (for event reading) ===
            if self.streamer_oauth_token and self.streamer_refresh_token:
                logger.info("[TwitchClient] Authenticating streamer account for events...")
                self.twitch_streamer = await Twitch(self.app_id, self.app_secret)

                try:
                    await self.twitch_streamer.set_user_authentication(self.streamer_oauth_token, self.streamer_scopes, self.streamer_refresh_token)
                    users = []
                    async for user in self.twitch_streamer.get_users():
                        users.append(user)
                        break
                    if users:
                        logger.info("[TwitchClient] Streamer account authenticated successfully")
                    else:
                        raise Exception("Streamer token validation failed")
                except Exception as e:
                    logger.warning(f"[TwitchClient] Streamer tokens failed ({str(e)}), will use bot account for events")
                    self.twitch_streamer = None
            else:
                logger.info("[TwitchClient] No streamer tokens provided, using bot account for events")
                self.twitch_streamer = None

            # === Create Chat Instance ===
            self.chat = await Chat(self.twitch_bot)

            self._register_event_handlers()

            self.chat.start()

            logger.info(f"[TwitchClient] Connected to Twitch channel: {self.channel_name}")
            logger.info("[TwitchClient] Chat operations: bot account | Event monitoring: streamer account" if self.twitch_streamer else "[TwitchClient] All operations: bot account")
            self.connected = True
            return True

        except Exception as e:
            logger.error(f"[TwitchClient] Failed to connect to Twitch: {e}")
            return False

    def _register_event_handlers(self):
        """Register event handlers for chat and EventSub events."""
        if not self.chat:
            return

        self.chat.register_event(ChatEvent.READY, self._on_ready)

        self.chat.register_event(ChatEvent.MESSAGE, self._on_message)

        self.chat.register_event(ChatEvent.SUB, self._on_subscription)

        self.chat.register_event(ChatEvent.RAID, self._on_raid)

    async def _on_ready(self, ready_event: EventData):
        """Handle bot ready event."""
        logger.info("[TwitchClient] Bot is ready, joining channel...")
        try:
            await ready_event.chat.join_room(self.channel_name)
            logger.info(f"[TwitchClient] Joined channel: {self.channel_name}")
        except Exception as e:
            logger.error(f"[TwitchClient] Failed to join channel: {e}")

    async def _on_message(self, msg: ChatMessage):
        """Handle incoming chat messages."""
        try:
            author = msg.user.name
            content = msg.text.strip()

            if not content:
                return

            logger.debug(f"[TwitchClient] Message from {author}: {content}")

            if self.message_handler:
                await self.message_handler(author, content, datetime.now())

        except Exception as e:
            logger.error(f"[TwitchClient] Error handling message: {e}")

    async def _on_subscription(self, sub: ChatSub):
        """Handle subscription events."""
        try:
            logger.info(f"[TwitchClient] New subscription in {sub.room.name}: {sub.sub_plan}")

            if self.event_handler:
                event_data = {
                    'type': 'subscription',
                    'user': getattr(sub, 'user', {}).get('name', 'unknown'),
                    'plan': sub.sub_plan,
                    'message': getattr(sub, 'sub_message', ''),
                    'timestamp': datetime.now()
                }
                await self.event_handler(event_data)

        except Exception as e:
            logger.error(f"[TwitchClient] Error handling subscription: {e}")

    async def _on_raid(self, raid_event: EventData):
        """Handle raid events."""
        try:
            raider_name = getattr(raid_event, 'from_broadcaster_user_name', 'unknown')
            viewer_count = getattr(raid_event, 'viewers', 0)
            logger.info(f"[TwitchClient] Raid from {raider_name} with {viewer_count} viewers")

            if self.event_handler:
                event_data = {
                    'type': 'raid',
                    'raider': raider_name,
                    'viewers': viewer_count,
                    'timestamp': datetime.now()
                }
                await self.event_handler(event_data)

        except Exception as e:
            logger.error(f"[TwitchClient] Error handling raid: {e}")

    async def send_message(self, message: str) -> bool:
        """
        Send a message to the connected channel.

        Args:
            message: Message content to send

        Returns:
            bool: True if sent successfully, False otherwise
        """
        if not self.chat or not self.connected:
            logger.warning("[TwitchClient] Cannot send message - not connected")
            return False

        try:
            room = self.chat.get_room(self.channel_name)
            if room:
                await room.send(message)
                logger.debug(f"[TwitchClient] Sent message: {message}")
                return True
            else:
                logger.error(f"[TwitchClient] Could not find room: {self.channel_name}")
                return False

        except Exception as e:
            logger.error(f"[TwitchClient] Failed to send message: {e}")
            return False

    async def disconnect(self):
        """Disconnect from Twitch and clean up resources."""
        logger.info("[TwitchClient] Disconnecting from Twitch...")

        try:
            if self.chat:
                self.chat.stop()

            if self.twitch_bot:
                await self.twitch_bot.close()

            if self.twitch_streamer:
                await self.twitch_streamer.close()

            self.connected = False
            logger.info("[TwitchClient] Disconnected successfully")

        except Exception as e:
            logger.error(f"[TwitchClient] Error during disconnect: {e}")

    async def run_forever(self):
        """Run the client indefinitely until stopped."""
        while True:
            try:
                if not self.connected:
                    logger.warning("[TwitchClient] Connection lost, attempting to reconnect...")
                    await asyncio.sleep(5)
                    await self.connect()
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"[TwitchClient] Error in run_forever: {e}")
                await asyncio.sleep(5)

    # === Command Registration ===
    def register_command(self, command_name: str, handler):
        """Register a chat command handler."""
        try:
            if self.chat:
                self.chat.register_command(command_name, handler)
                logger.info(f"[TwitchClient] Registered command: {command_name}")
            else:
                logger.warning("[TwitchClient] Cannot register command - chat not initialized")
        except Exception as e:
            logger.error(f"[TwitchClient] Error registering command {command_name}: {e}")

    # === EventSub Integration (Future Enhancement) ===
    async def setup_eventsub(self):
        """
        Set up EventSub for follow, subscription, and raid events.
        This would use webhook or websocket transport.
        """
        try:
            logger.info("[TwitchClient] EventSub setup not yet implemented")
            pass
        except Exception as e:
            logger.error(f"[TwitchClient] Error in setup_eventsub: {e}")