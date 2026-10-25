"""
Twitch input listener (Service + mixins).

LAYER: Input (see ARCHITECTURE.md)

This is the dedicated Service responsible for maintaining a persistent
connection to Twitch (chat + EventSub) and translating raw Twitch events
into the internal event system.

It uses a composition of mixins for clean separation:
- TwitchAuthMixin: OAuth, token refresh, bot + streamer clients
- TwitchEventsMixin: mapping of chat / subscription / follow events
- TwitchWebsocketSubMixin: EventSub subscription management

Core responsibilities (strictly limited):
- Long-running _run loop that keeps the connection alive
- Ensure connected state with retries (_ensure_connected)
- Forward incoming Twitch events as internal Event objects onto the bus
- Clean shutdown of all Twitch resources

It must never contain decision logic, memory writes, or output handling.
Those are routed via EventProcessors (MemoryWriter, Processing layers, etc.).

Part of the 2026 input layer cleanup: split from monolithic listener into
focused mixins + this coordinator Service.
"""

import asyncio
from typing import Any
from twitchAPI.eventsub.websocket import EventSubWebsocket

from src.qubit.core.service import Service
from src.qubit.input.twitch.events import TwitchEventsMixin
from src.qubit.input.twitch.auth import TwitchAuthMixin
from src.qubit.input.twitch.subscriptions import TwitchWebsocketSubMixin


class TwitchListener(Service, TwitchAuthMixin, TwitchEventsMixin, TwitchWebsocketSubMixin):
    """
    Long-lived Service that connects to Twitch and pumps events into the system.

    It owns the Twitch client instances (bot + streamer) and the EventSub
    websocket. All raw Twitch activity is normalized and published as internal
    events for the rest of the pipeline (Processing → Cognitive → Generation → Output).

    The listener is feature-flagged ("twitch") and gracefully degrades when disabled.
    """

    def __init__(self, settings):
        super().__init__("twitch")
        self.settings = settings
        self.twitch_bot = None
        self.twitch_streamer = None
        self.chat = None
        self.eventsub = None
        self.connected = False


    def attach(self, app) -> None:
        super().attach(app)


    async def _run(self: Any) -> None:
        """
        Main service loop for the Twitch connection.

        Responsibilities:
        - Respect global start/shutdown and the "twitch" feature flag
        - Maintain connection via _ensure_connected + periodic token refresh
        - On error: clean stop + short backoff before retry

        This loop runs at low frequency (hourly refresh) because the actual
        chat and EventSub traffic is handled asynchronously via the mixins.
        """
        while not self.app.state.shutdown.is_set():
            if not self.app.state.start.is_set() or not self.app.state.features.twitch:
                await asyncio.sleep(1)
                continue

            await self._ensure_connected()
            await self._refresh_tokens()
            await asyncio.sleep(60 * 60)

    async def _ensure_connected(self: Any) -> None:
        """
        Idempotent connection bootstrap for Twitch clients and EventSub.

        Called from the main loop. On failure it logs and returns (retry happens
        on next cycle). Once connected it also starts the EventSub websocket
        and subscribes to follow events.
        """
        if self.connected:
            return

        self.connected = await self._start_client()
        if not self.connected:
            self._set_disconnected("auth failed")
            self.logger.error("[_ensure_connected] Failed to connect — supervisor will retry")
            raise ConnectionError("Twitch connection failed")

        self.eventsub = EventSubWebsocket(self.twitch_streamer)
        self.eventsub.start()
        await self._subscribe_to_follow_events()
        self._set_connected()


    async def _start_client(self: Any) -> bool:
        """
        Perform the full authentication + chat setup sequence.

        Returns True only if bot + streamer auth and chat connection all succeed.
        Any failure returns False so the caller can retry.
        """
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


    async def stop(self: Any)  -> None:
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
        self._set_disconnected()
        self.logger.info("[stop] Disconnected successfully.")
        await super().stop()