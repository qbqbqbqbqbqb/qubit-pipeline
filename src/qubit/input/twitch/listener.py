import asyncio
from twitchAPI.eventsub.websocket import EventSubWebsocket

from src.qubit.core.service import Service
from src.qubit.input.twitch.events import TwitchEventsMixin
from src.qubit.input.twitch.auth import TwitchAuthMixin
from src.qubit.input.twitch.subscriptions import TwitchWebsocketSubMixin

class TwitchListener(Service, TwitchAuthMixin, TwitchEventsMixin, TwitchWebsocketSubMixin):
    def __init__(self, settings):
        super().__init__("twitch")
        self.settings = settings
        self.twitch_bot = None
        self.twitch_streamer = None
        self.chat = None
        self.eventsub = None
        self.connected = False


    async def start(self, app) -> None:
        await super().start(app)


    # TODO: split this up, a lot happening
    async def _run(self) -> None:
        await super()._run()
        while not self.app.state.shutdown.is_set():
            twitch_enabled = self.app.state.features.get("twitch", True)

            self.logger.debug("[_run] TwitchListener loop - start: {self.app.state.start.is_set()}, twitch_enabled: {twitch_enabled}, connected: {self.connected}")
            if not self.app.state.start.is_set() or not twitch_enabled:
                await asyncio.sleep(1)
                continue

            if twitch_enabled:
                try:
                    if not self.connected:
                        self.connected = await self._start_client()
                        if not self.connected:
                            self.logger.error("[_run]Failed to connect. Retrying in 10s...")
                            await asyncio.sleep(10)
                            continue

                        self.eventsub = EventSubWebsocket(self.twitch_streamer)
                        self.eventsub.start()
                        await self._subscribe_to_follow_events()

                    await self._refresh_tokens()
                    await asyncio.sleep(60 * 60)

                except Exception as e:
                    self.logger.error("[_run] Listener error: %s. Restarting...", e)
                    await self.stop()
                    await asyncio.sleep(5)


    async def _start_client(self) -> bool:
        self.logger.info("[_start_client] Starting TwitchClient...")
        try:
            await self._authenticate_bot_account()
            await self._authenticate_streamer_account()
            await self._setup_chat()
            self.logger.info("[_start_client] Connected to Twitch channel: %s",
                             self.settings.twitch_channel)
            return True
        except Exception as e:
            self.logger.error("[_start_client] Failed to connect TwitchClient: %s", e)
            return False


    async def stop(self)  -> None:
        """
        Disconnect from Twitch services.

        Stops the chat monitoring, closes bot and streamer Twitch clients,
        and updates the connection status.

        Returns:
            None
        """
        self.logger.info("[stop] Disconnecting TwitchClient...")
        if self.chat:
            self.chat.stop()
        if self.twitch_bot:
            await self.twitch_bot.close()
        if self.twitch_streamer:
            await self.twitch_streamer.close()
        if self.eventsub:
            await self.eventsub.stop()
        self.connected = False
        self.logger.info("[stop] Disconnected successfully.")
        await super().stop()
