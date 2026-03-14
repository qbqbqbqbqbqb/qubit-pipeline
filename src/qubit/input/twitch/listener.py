import asyncio
from datetime import datetime, timedelta, timezone
from twitchAPI.twitch import Twitch
from twitchAPI.type import AuthScope, ChatEvent
from twitchAPI.chat import Chat, ChatMessage, EventData
from twitchAPI.oauth import UserAuthenticator, refresh_access_token
from twitchAPI.eventsub.websocket import EventSubWebsocket
from twitchAPI.object.eventsub import ChannelFollowEvent

from src.qubit.core import app
from src.qubit.core.service import Service
from src.qubit.input.twitch.events import TwitchEvents
from src.utils.log_utils import get_logger
from src.qubit.input.twitch.auth import TwitchAuth
from src.qubit.input.twitch.subscriptions import TwitchWebsocketSub

class TwitchListener(Service, TwitchAuth, TwitchEvents, TwitchWebsocketSub):
    def __init__(self, settings):
        super().__init__("twitch")
        self.settings = settings
        self.logger = get_logger(__name__)
        self.twitch_bot = None
        self.twitch_streamer = None
        self.chat = None
        self.eventsub = None
        self.connected = False

    async def start(self, app):
        self.app = app
        self.event_bus = app.event_bus

        twitch_enabled = app.state.features.get("twitch", True)

        while not self.app.state.shutdown.is_set():
            if not self.app.state.start.is_set():
                await asyncio.sleep(1)
                continue

            while twitch_enabled:
                try:
                    if not self.connected:
                        self.connected = await self._start_client()
                        if not self.connected:
                            self.logger.error("Failed to connect. Retrying in 10s...")
                            await asyncio.sleep(10)
                            continue

                        self.eventsub = EventSubWebsocket(self.twitch_streamer)
                        self.eventsub.start()
                        await self._subscribe_to_follow_events()

                    await self._refresh_tokens()
                    await asyncio.sleep(60 * 60)

                except Exception as e:
                    self.logger.error(f"Listener error: {e}. Restarting...")
                    await self.stop()
                    await asyncio.sleep(5)
            await super().start(app)

    async def _start_client(self) -> bool:
        self.logger.info("[start] Starting TwitchClient...")
        try:
            await self._authenticate_bot_account()
            await self._authenticate_streamer_account()
            await self._setup_chat()
            self.logger.info(f"[start] Connected to Twitch channel: {self.settings.twitch_channel}")
            return True
        except Exception as e:
            self.logger.error(f"[start] Failed to connect TwitchClient: {e}")
            return False

    async def stop(self):
        """
        Disconnect from Twitch services.

        Stops the chat monitoring, closes bot and streamer Twitch clients,
        and updates the connection status.

        Returns:
            None
        """
        self.logger.info("[disconnect] Disconnecting TwitchClient...")
        if self.chat:
            self.chat.stop()
        if self.twitch_bot:
            await self.twitch_bot.close()
        if self.twitch_streamer:
            await self.twitch_streamer.close()
        if self.eventsub:
            await self.eventsub.stop()
        self.connected = False
        self.logger.info("[disconnect] Disconnected successfully.")
