"""
Kick input listener (Service + mixins).

LAYER: Input

Pure HTTP + Pusher WebSocket implementation (no third-party Kick client).
Mirrors the structure of the Twitch listener.

Core responsibilities:
- Long-running _run loop respecting "kick" feature flag
- OAuth + token management via KickAuthMixin
- Chat + event pumping via KickEventsMixin (Pusher WS)
- Graceful shutdown
"""

import asyncio
from typing import Any

from src.qubit.core.service import Service
from src.qubit.input.kick.events import KickEventsMixin
from src.qubit.input.kick.auth import KickAuthMixin


class KickListener(Service, KickAuthMixin, KickEventsMixin):
    """
    Long-lived Service that connects to Kick (pure HTTP + Pusher WS)
    and pumps chat/events into the internal EventBus as kick_* raw events.
    """

    def __init__(self, settings):
        super().__init__("kick")
        self.settings = settings
        self.kick_bot = None
        self.kick_streamer = None
        self.chat_ws = None  # pusher websocket
        self.connected = False
        self.chatroom_id = None

    async def start(self, app) -> None:
        await super().start(app)

    async def _run(self: Any) -> None:
        await super()._run()
        while not self.app.state.shutdown.is_set():
            kick_enabled = self.app.state.features.get("kick", True)

            self.logger.debug("[_run] KickListener loop - start: %s, kick_enabled: %s, connected: %s",
                              self.app.state.start.is_set(), kick_enabled, self.connected)
            if not self.app.state.start.is_set() or not kick_enabled:
                await asyncio.sleep(1)
                continue

            if kick_enabled:
                try:
                    await self._ensure_connected()
                    await self._refresh_tokens()
                    await asyncio.sleep(60 * 60)
                except Exception as e:
                    self.logger.error("[_run] Kick listener error: %s. Restarting...", e)
                    await self.stop()
                    await asyncio.sleep(5)

    async def _ensure_connected(self: Any) -> None:
        if self.connected:
            return

        self.connected = await self._start_client()
        if not self.connected:
            self.logger.error("[_ensure_connected] Failed to connect Kick. Retrying in 10s...")
            await asyncio.sleep(10)
            return

        # Start the Pusher WS listener for chat + events (non-blocking)
        await self._start_pusher_listener()

    async def _start_client(self: Any) -> bool:
        self.logger.info("[_start_client] Starting KickClient...")
        try:
            await self._authenticate_bot_account()
            await self._authenticate_streamer_account()
            await self._resolve_chatroom_id()
            self.logger.info("[_start_client] Connected to Kick channel: %s (chatroom=%s)",
                             self.settings.kick_channel, self.chatroom_id)
            return True
        except Exception as e:
            self.logger.error("[_start_client] Failed to connect KickClient: %s", e)
            return False

    async def _resolve_chatroom_id(self: Any) -> None:
        """Resolve chatroom ID (needed for Pusher WS)."""
        if self.settings.kick_chatroom_id:
            self.chatroom_id = self.settings.kick_chatroom_id
            self.logger.info("[_resolve_chatroom_id] Using manual KICK_CHATROOM_ID: %s", self.chatroom_id)
            return

        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                url = f"https://kick.com/api/v2/channels/{self.settings.kick_channel}"
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        chatroom = data.get("chatroom") or {}
                        cid = chatroom.get("id") or data.get("chatroom_id")
                        if cid:
                            self.chatroom_id = int(cid)
                            self.logger.info("[_resolve_chatroom_id] Resolved chatroom_id=%s", self.chatroom_id)
                            return
        except Exception as e:
            self.logger.warning("[_resolve_chatroom_id] Failed to resolve chatroom: %s", e)

        self.chatroom_id = None

    async def _start_pusher_listener(self: Any) -> None:
        """Launch background task that maintains Pusher WS connection for Kick chat/events."""
        if self.chatroom_id is None:
            self.logger.warning("[_start_pusher_listener] No chatroom_id; chat input disabled for now")
            return
        # Fire and forget the WS loop (handled in events mixin)
        asyncio.create_task(self._run_pusher_ws())

    async def stop(self: Any) -> None:
        self.logger.info("[stop] Disconnecting KickClient...")
        if self.chat_ws:
            try:
                await self.chat_ws.close()
            except Exception:
                pass
        if self.kick_bot:
            await self.kick_bot.close()
        if self.kick_streamer:
            await self.kick_streamer.close()
        self.connected = False
        self.logger.info("[stop] Kick disconnected.")
        await super().stop()
