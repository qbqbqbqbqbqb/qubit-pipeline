import asyncio
from datetime import datetime, timedelta, timezone
from twitchAPI.twitch import Twitch
from twitchAPI.type import AuthScope, ChatEvent
from twitchAPI.chat import Chat, ChatMessage, EventData
from twitchAPI.oauth import UserAuthenticator, refresh_access_token
from twitchAPI.eventsub.websocket import EventSubWebsocket
from twitchAPI.object.eventsub import ChannelFollowEvent

from src.qubit.input.twitch.events import TwitchEvents
from src.qubit.utils.log_utils import get_logger
from src.qubit.input.twitch.auth import TwitchAuth
from src.qubit.input.twitch.subscriptions import TwitchWebsocketSub

class TwitchListener(TwitchAuth, TwitchEvents, TwitchWebsocketSub):
    def __init__(self, settings, twitch_enabled = None,
                 chat_enabled = None, raid_enabled = None, 
                 follow_enabled = None, subs_enabled = None):
        self.settings = settings
        self.logger = get_logger(__name__)
        self.twitch_bot = None
        self.twitch_streamer = None
        self.chat = None
        self.eventsub = None
        self.connected = False
        self.twitch_enabled = twitch_enabled
        self.chat_enabled = chat_enabled
        self.raid_enabled = raid_enabled
        self.follow_enabled = follow_enabled
        self.subs_enabled = subs_enabled


    async def listen(self, event_bus):
        self.event_bus = event_bus 
        while self.twitch_enabled.is_set():   
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
                await self._disconnect()
                await asyncio.sleep(5)

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

    async def disconnect(self):
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
