import asyncio
import datetime as dt
from twitchAPI.twitch import Twitch
from twitchAPI.type import AuthScope, ChatEvent
from twitchAPI.chat import Chat, EventData, ChatMessage, ChatSub
from twitchAPI.oauth import UserAuthenticator
from scripts.utils.log_utils import get_logger
from scripts.core.base_module import BaseModule


class TwitchClient(BaseModule):
    def __init__(self, settings, signals, monologue_module, queue_manager):
        super().__init__("TwitchModule", logger=get_logger("TwitchModule"))
        self.settings = settings

        self.twitch_bot = None
        self.twitch_streamer = None
        self.chat = None
        self.accounts_connected = False
        self._running = False

        self.signals = signals
        self.monologue_module = monologue_module
        self.queue_manager = queue_manager 

        self.bot_scopes = [
            AuthScope.CHAT_READ,
            AuthScope.CHAT_EDIT
        ]

        self.streamer_scopes = [
            AuthScope.CHANNEL_READ_SUBSCRIPTIONS,
            AuthScope.CHANNEL_MANAGE_RAIDS
        ]

    async def run(self):
        self.logger.info("[run] Starting TwitchClient module...")
        connected = await self._start_client()
        
        if not connected:
            self.logger.error("Failed to connect Twitch client. Exiting TwitchModule.")
            return

        self._running = True

        try:
            while self._running:
                await asyncio.sleep(1)  
        except asyncio.CancelledError:
            self.logger.info("[run] TwitchClient run cancelled.")
        finally:
            await self.disconnect()

    async def _start_client(self) -> bool:
        self.logger.info("[start] Starting TwitchClient...")
        try:
            await self._authenticate_bot_account()
            await self._authenticate_streamer_account()
            await self._setup_chat()
            self.accounts_connected = True
            self.logger.info(f"[start] Connected to Twitch channel: {self.settings.twitch_channel}")
            return True
        except Exception as e:
            self.logger.error(f"[start] Failed to connect TwitchClient: {e}")
            return False

    async def _authenticate_bot_account(self):
        self.logger.info("[_authenticate_bot_account] Authenticating bot account...")
        self.twitch_bot = Twitch(self.settings.twitch_client_id, self.settings.twitch_client_secret)
        if not self.settings.bot_oauth_token:
            self.logger.info("[_authenticate_bot_account] No bot OAuth token found, authenticating interactively...")
            auth = UserAuthenticator(self.twitch_bot, self.bot_scopes)
            token, refresh_token = await auth.authenticate()
            self.settings.bot_oauth_token = token
            self.settings.bot_refresh_token = refresh_token

        await self.twitch_bot.set_user_authentication(
            self.settings.bot_oauth_token,
            self.bot_scopes,
            self.settings.bot_refresh_token
        )

    async def _authenticate_streamer_account(self):
        if not self.settings.streamer_oauth_token or not self.settings.streamer_refresh_token:
            self.logger.info("[_authenticate_streamer_account] No streamer OAuth token found, authenticating interactively...")
            auth = UserAuthenticator(self.twitch_bot, self.streamer_scopes)
            token, refresh_token = await auth.authenticate()
            self.settings.streamer_oauth_token = token
            self.settings.streamer_refresh_token = refresh_token
        else:
            self.logger.info("[_authenticate_streamer_account] Authenticating streamer account...")
            self.twitch_streamer = Twitch(self.settings.twitch_client_id, self.settings.twitch_client_secret)
            await self.twitch_streamer.set_user_authentication(
                self.settings.streamer_oauth_token,
                self.streamer_scopes,
                self.settings.streamer_refresh_token
            )

    async def _setup_chat(self):
        self.chat = await Chat(self.twitch_bot)
        self.chat.register_event(ChatEvent.READY, self._on_ready)
        self.chat.register_event(ChatEvent.MESSAGE, self._on_message)
        self.chat.register_event(ChatEvent.SUB, self._on_subscription)
        self.chat.register_event(ChatEvent.RAID, self._on_raid)
        self.chat.start()

    async def _on_ready(self, event: EventData):
        try:
            self.logger.info("[_on_ready] Bot ready, joining channel...")
            await event.chat.join_room(self.settings.twitch_channel)
            self.logger.info(f"[_on_ready] Joined channel: {self.settings.twitch_channel}")
        except Exception as e:
            self.logger.error(f"[_on_ready] Failed to join channel: {e}")

    async def _on_message(self, msg: ChatMessage):
        try:
            author = msg.user.name
            content = msg.text.strip()
            timestamp_ms = msg.sent_timestamp

            timestamp = None
            if timestamp_ms:
                timestamp = dt.datetime.fromtimestamp(timestamp_ms / 1000)

            self.logger.debug(f"[_on_message] Message from {author}: {content}")

            content_lower = content.lower()
            if content_lower == "!qubit start":
                self.signals.monologue_enabled = True
                self.monologue_module.resume()
                self.logger.info("[_on_message] Monologue started via chat command !qubit start")
                return

            if content_lower == "!qubit stop":
                self.signals.monologue_enabled = False
                self.monologue_module.pause()
                self.logger.info("[_on_message] Monologue stopped via chat command !qubit stop")
                return
            
            await self.queue_manager.chat_queue.put({
                "user": author,
                "prompt": content,
                "timestamp": timestamp or dt.datetime.now(),
                "type": "chat_message"
            })

            self.logger.info("[_on_message] Chat message enqueued in chat_queue")

        except Exception as e:
            self.logger.error(f"[_on_message] Error handling message: {e}")

    async def _on_subscription(self, sub: ChatSub):
        try:
            self.logger.info(f"[_on_subscription] New subscription in {sub.room.name}: {sub.sub_plan}")
        except Exception as e:
            self.logger.error(f"[_on_subscription] Error handling subscription: {e}")

    async def _on_raid(self, raid_event: EventData):
        try:
            raider_name = getattr(raid_event, 'from_broadcaster_user_name', 'unknown')
            viewer_count = getattr(raid_event, 'viewers', 0)
            self.logger.info(f"[_on_raid] Raid from {raider_name} with {viewer_count} viewers")
        except Exception as e:
            self.logger.error(f"[_on_raid] Error handling raid: {e}")

    async def disconnect(self):
        self.logger.info("[disconnect] Disconnecting TwitchClient...")
        if self.chat is not None:
            self.chat.stop()
        if self.twitch_bot:
            await self.twitch_bot.close()
        if self.twitch_streamer:
            await self.twitch_streamer.close()
        self.accounts_connected = False
        self.logger.info("[disconnect] Disconnected successfully.")

    async def stop(self):
        await self.disconnect()
        await super().stop()
