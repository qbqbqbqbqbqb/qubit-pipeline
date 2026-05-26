"""
Kick events handling mixin.

Uses a raw websockets connection to Kick's Pusher endpoint to receive
real-time chat messages + social events (follow, subscription, raid/kick).

Publishes raw KickChatEvent, KickFollowEvent etc to the bus (mirrors twitch/events.py).
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any
import websockets

from src.qubit.core.events import (
    KickChatEvent,
    KickFollowEvent,
    KickRaidEvent,
    KickSubscriptionEvent,
)

PUSHER_URL = "wss://ws-us2.pusher.com/app/32cbd69e4b950bf97679?protocol=7&client=js&version=8.4.0-rc2&flash=false"


class KickEventsMixin:
    """
    Mixin providing Kick Pusher-WS based event listening.
    Expected host attrs: logger, settings, chatroom_id, event_bus (via app)
    """
    logger: logging.Logger
    app: Any

    async def _run_pusher_ws(self: Any) -> None:
        """Maintain Pusher WS connection and dispatch messages."""
        room = self.chatroom_id or getattr(self, "chatroom_id", None)
        if not room:
            self.logger.error("[_run_pusher_ws] No chatroom_id available")
            return

        channels_to_sub = [
            f"chatrooms.{room}.v2",
            f"chatroom_{room}",
            f"chatrooms.{room}",
        ]

        shutdown = getattr(self.app, "state", None) and getattr(self.app.state, "shutdown", None)
        while not (getattr(shutdown, "is_set", lambda: False)() if shutdown else False):
            try:
                async with websockets.connect(PUSHER_URL) as ws:
                    self.chat_ws = ws
                    self.logger.info("[KickWS] Connected to Pusher for Kick chatroom %s", room)

                    # Subscribe
                    for ch in channels_to_sub:
                        await ws.send(json.dumps({
                            "event": "pusher:subscribe",
                            "data": {"auth": "", "channel": ch}
                        }))

                    async for raw in ws:
                        try:
                            msg = json.loads(raw)
                            await self._handle_pusher_message(msg)
                        except Exception as inner:
                            self.logger.debug("[KickWS] bad msg: %s (%s)", raw, inner)
            except Exception as e:
                self.logger.warning("[KickWS] WS error or disconnect: %s. Reconnecting in 5s...", e)
                await asyncio.sleep(5)

    async def _handle_pusher_message(self: Any, msg: dict) -> None:
        event = msg.get("event", "")
        data_str = msg.get("data", "{}")
        try:
            data = json.loads(data_str) if isinstance(data_str, str) else data_str
        except Exception:
            data = {}

        # Common Kick event names (observed across libs/gists)
        if "ChatMessage" in event or event.endswith("ChatMessageEvent") or "message.sent" in event.lower():
            await self._on_kick_chat(data)
        elif "Follow" in event or "follow" in event.lower():
            await self._on_kick_follow(data)
        elif "Subscription" in event or "sub" in event.lower():
            await self._on_kick_subscription(data)
        elif "Raid" in event or "raid" in event.lower() or "Kick" in event:  # gifted kicks etc
            await self._on_kick_raid(data)
        elif event == "pusher:connection_established":
            self.logger.debug("[KickWS] pusher connected")
        else:
            # Debug unknown events (useful for extending)
            if event and not event.startswith("pusher:"):
                self.logger.debug("[KickWS] unhandled event: %s -> %s", event, data)

    async def _on_kick_chat(self: Any, data: dict) -> None:
        chat_enabled = self.app.state.features.get("chat", True)
        if not chat_enabled:
            return
        try:
            # Kick payload shapes vary; try common keys from different sources
            user = (data.get("sender") or data.get("user") or {}).get("username") or data.get("sender_username") or "Anonymous"
            text = data.get("content") or data.get("message") or data.get("text") or ""
            if not text:
                return

            self.logger.debug("[_on_kick_chat] %s: %s", user, text)

            event = KickChatEvent(
                type="kick_chat",
                data={"user": user, "text": text, "source": "kick"},
                user=user,
                text=text,
                timestamp=datetime.now(timezone.utc).isoformat()
            )
            await self.event_bus.publish(event)
            self.logger.info("[_on_kick_chat] Published kick chat")
        except Exception as e:
            self.logger.error("[_on_kick_chat] error: %s", e)

    async def _on_kick_follow(self: Any, data: dict) -> None:
        follow_enabled = self.app.state.features.get("follow", True)
        if not follow_enabled:
            return
        try:
            user = data.get("user", {}).get("username") or data.get("follower") or data.get("username") or "Someone"
            followed_at = data.get("followed_at") or datetime.now(timezone.utc).isoformat()

            self.logger.info("[_on_kick_follow] %s followed", user)

            event = KickFollowEvent(
                type="kick_follow",
                data={"user": user, "followed_at": followed_at},
                user=user,
                followed_at=followed_at,
                timestamp=datetime.now(timezone.utc).isoformat()
            )
            await self.event_bus.publish(event)
        except Exception as e:
            self.logger.error("[_on_kick_follow] error: %s", e)

    async def _on_kick_subscription(self: Any, data: dict) -> None:
        subs_enabled = self.app.state.features.get("subs", True)
        if not subs_enabled:
            return
        try:
            user = (data.get("subscriber") or data.get("user") or {}).get("username") or data.get("username") or "Someone"
            tier = str(data.get("tier") or data.get("subscription_tier") or "1")
            sub_type = data.get("type") or "subscription"
            sub_msg = data.get("message") or ""

            self.logger.info("[_on_kick_subscription] %s sub %s", user, tier)

            event = KickSubscriptionEvent(
                type="kick_subscription",
                data={"user": user, "tier": tier, "sub_type": sub_type, "sub_message": sub_msg},
                user=user,
                tier=tier,
                sub_type=sub_type,
                sub_message=sub_msg,
                timestamp=datetime.now(timezone.utc).isoformat()
            )
            await self.event_bus.publish(event)
        except Exception as e:
            self.logger.error("[_on_kick_subscription] error: %s", e)

    async def _on_kick_raid(self: Any, data: dict) -> None:
        raid_enabled = self.app.state.features.get("raid", True)
        if not raid_enabled:
            return
        try:
            raider = (data.get("raider") or data.get("user") or {}).get("username") or data.get("from") or "Someone"
            viewers = int(data.get("viewers") or data.get("count") or 0)

            self.logger.info("[_on_kick_raid] %s raiding with %s", raider, viewers)

            event = KickRaidEvent(
                type="kick_raid",
                data={"user": raider, "viewers": viewers},
                user=raider,
                viewers=viewers,
                timestamp=datetime.now(timezone.utc).isoformat()
            )
            await self.event_bus.publish(event)
        except Exception as e:
            self.logger.error("[_on_kick_raid] error: %s", e)
