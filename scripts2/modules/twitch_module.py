import asyncio
from twitchAPI.twitch import Twitch
from twitchAPI.type import AuthScope, ChatEvent
from twitchAPI.chat import Chat, ChatMessage, EventData
from twitchAPI.oauth import UserAuthenticator

from scripts2.modules.base_module import BaseModule
from scripts2.utils.log_utils import get_logger
from scripts2.config.config import STREAMER_SCOPES, BOT_SCOPES

class TwitchModule(BaseModule):
    def __init__(self, settings, signals, event_broker, twitch_enabled=True, chat_enabled=True):
        super().__init__(name="TwitchModule")
        self.settings = settings
        self.signals = signals
        self.twitch_enabled = twitch_enabled
        self.chat_enabled = chat_enabled
        self.event_broker = event_broker 
        self.twitch_bot = None
        self.twitch_streamer = None
        self.chat = None

    async def start(self):
        if not self.twitch_enabled:
            self.logger.info(f"[start] {self.name} is disabled. Not starting.")
            return
        await super().start()

    async def run(self):
        await super().run()
        connected = await self._start_client()

        if not connected:
            self.logger.error("Failed to connect Twitch client. Exiting TwitchModule.")
            self._running = False
            await self.stop()
            return
    
        while self._running:
            self.logger.info("[run] Twitch module is running...")
            await asyncio.sleep(600)

    async def disconnect(self):
        self.logger.info("[disconnect] Disconnecting TwitchClient...")
        if self.chat is not None and self.chat_enabled is True:
            self.chat.stop()
        if self.twitch_bot:
            await self.twitch_bot.close()
        if self.twitch_streamer:
            await self.twitch_streamer.close()
        self.connected = False
        self.logger.info("[disconnect] Disconnected successfully.")

    async def stop(self):
        await self.disconnect()
        await super().stop()

    async def _start_client(self) -> bool:
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
        if not self.settings.bot_oauth_token or not self.settings.bot_refresh_token:
            self.logger.info("[_authenticate_streamer_account] No streamer OAuth token found, authenticating interactively...")
            auth = UserAuthenticator(self.twitch_bot, BOT_SCOPES)
            token, refresh_token = await auth.authenticate()
            self.settings.bot_oauth_token = token
            self.settings.bot_refresh_token = refresh_token
        else:
            self.logger.info("[_authenticate_streamer_account] Authenticating streamer account...")
            self.twitch_bot = Twitch(self.settings.twitch_client_id, self.settings.twitch_client_secret)
            await self.twitch_bot.set_user_authentication(
                self.settings.bot_oauth_token,
                BOT_SCOPES,
                self.settings.bot_refresh_token
            )

    async def _authenticate_streamer_account(self):
        if not self.settings.streamer_oauth_token or not self.settings.streamer_refresh_token:
            self.logger.info("[_authenticate_streamer_account] No streamer OAuth token found, authenticating interactively...")
            auth = UserAuthenticator(self.twitch_bot, STREAMER_SCOPES)
            token, refresh_token = await auth.authenticate()
            self.settings.streamer_oauth_token = token
            self.settings.streamer_refresh_token = refresh_token
        else:
            self.logger.info("[_authenticate_streamer_account] Authenticating streamer account...")
            self.twitch_streamer = Twitch(self.settings.twitch_client_id, self.settings.twitch_client_secret)
            await self.twitch_streamer.set_user_authentication(
                self.settings.streamer_oauth_token,
                STREAMER_SCOPES,
                self.settings.streamer_refresh_token
            )
    
    async def _setup_chat(self):
        self.chat = await Chat(self.twitch_bot)
        self.chat.register_event(ChatEvent.READY, self._on_ready)
        self.chat.register_event(ChatEvent.MESSAGE, self._on_message)
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
            message = msg.text.strip()

            self.logger.debug(f"[_on_message] Message from {author}: {message}")

            self.event_broker.publish_event({
                "type": "twitch_chat",
                "user": author,
                "text": message
            })

            self.logger.info("[_on_message] Chat message published to broker")

        except Exception as e:
            self.logger.error(f"[_on_message] Error handling message: {e}")