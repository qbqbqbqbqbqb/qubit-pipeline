"""
Moderation processor (pure EventProcessor).

LAYER: Input Processing

This component is the first filter in the input pipeline. It receives raw
Twitch events (chat, subscriptions, raids, follows) and produces sanitized
*_processed events for downstream layers.

Responsibilities:
- Detect and filter banned words using the shared filter utilities
- Remove or sanitize problematic content before it reaches Cognitive or Memory
- Emit clean events (twitch_chat_processed, etc.) so that the rest of the
  system can assume input has already been moderated

This processor is intentionally narrow. It does not make decisions about
whether to respond — that belongs in the Cognitive layer.
"""

from src.qubit.core.event_processor import EventProcessor
from config.config import BLACKLISTED_WORDS_LIST, WHITELISTED_WORDS_LIST
from src.qubit.core.events import (
    TwitchChatEvent, 
    TwitchSubscriptionEvent,
    TwitchRaidEvent, 
    TwitchFollowEvent, 
    KickChatEvent,
    KickSubscriptionEvent,
    KickRaidEvent,
    KickFollowEvent,
    Event
)
from src.qubit.utils.filter_utils import contains_banned_words


class ModerationProcessor(EventProcessor):
    """
    Pure EventProcessor that sanitizes raw Twitch input events.

    It acts as a gatekeeper: any event that passes through is considered
    safe for storage in memory and for feeding into the decision engine.

    The processor emits new events with "_processed" suffix rather than
    mutating the originals.
    """

    SUBSCRIPTIONS = {
        "twitch_chat": "handle_event",
        "twitch_subscription": "handle_event",
        "twitch_raid": "handle_event",
        "twitch_follow": "handle_event",
        "kick_chat": "handle_event",
        "kick_subscription": "handle_event",
        "kick_raid": "handle_event",
        "kick_follow": "handle_event",
    }

    def __init__(self):
        super().__init__("moderation processor")

    async def handle_event(self, event: Event) -> None:
        """
        Entry point for all raw Twitch events.

        Dispatches to the appropriate moderation method based on event type.
        Each moderated event is published as a clean *_processed variant.
        """
        if isinstance(event, TwitchChatEvent):
            self.logger.info("[handle_event] Moderating twitch chat event: %s", event)
            await self._moderate_chat(event)
        elif isinstance(event, TwitchSubscriptionEvent):
            self.logger.info("[handle_event] Moderating twitch subscription event: %s", event)
            await self._moderate_subscription(event)
        elif isinstance(event, TwitchRaidEvent):
            self.logger.info("[handle_event] Moderating twitch raid event: %s", event)
            await self._moderate_raid(event)
        elif isinstance(event, TwitchFollowEvent):
            self.logger.info("[handle_event] Moderating twitch follow event: %s", event)
            await self._moderate_follow(event)
        elif isinstance(event, KickChatEvent):
            self.logger.info("[handle_event] Moderating kick chat event: %s", event)
            await self._moderate_kick_chat(event)
        elif isinstance(event, KickSubscriptionEvent):
            self.logger.info("[handle_event] Moderating kick subscription event: %s", event)
            await self._moderate_kick_subscription(event)
        elif isinstance(event, KickRaidEvent):
            self.logger.info("[handle_event] Moderating kick raid event: %s", event)
            await self._moderate_kick_raid(event)
        elif isinstance(event, KickFollowEvent):
            self.logger.info("[handle_event] Moderating kick follow event: %s", event)
            await self._moderate_kick_follow(event)
        else:
            self.logger.warning("[ModerationProcessor] Unknown event type: %s", event.type)

    async def _moderate_chat(self, event: TwitchChatEvent) -> None:
        """Sanitise username and message text, then publish a clean processed event."""
        sanitised_user = self._sanitise(event.user, default="Someone")
        sanitised_msg = self._sanitise(event.text, default="")

        sanitised_event = TwitchChatEvent(
            type="twitch_chat_processed",
            data={**event.data, "user": sanitised_user, "text": sanitised_msg},
            user=sanitised_user,
            text=sanitised_msg,
            timestamp=event.timestamp
        )
        await self.event_bus.publish(sanitised_event)

    async def _moderate_subscription(self, event: TwitchSubscriptionEvent) -> None:
        """Sanitise subscription events (user + optional sub message)."""
        sanitised_user = self._sanitise(event.user, default="Someone")
        sanitised_msg = self._sanitise(event.sub_message, default="")

        sanitised_event = TwitchSubscriptionEvent(
            type="twitch_subscription_processed",
            data={**event.data, "user": sanitised_user, "sub_message": sanitised_msg},
            user=sanitised_user,
            tier=event.tier,
            sub_type=event.sub_type,
            sub_message=sanitised_msg,
            timestamp=event.timestamp
        )
        await self.event_bus.publish(sanitised_event)

    async def _moderate_raid(self, event: TwitchRaidEvent) -> None:
        """Sanitise raid events (mainly the raider username)."""
        sanitised_user = self._sanitise(event.user, default="Someone")

        sanitised_event = TwitchRaidEvent(
            type="twitch_raid_processed",
            data={**event.data, "user": sanitised_user},
            user=sanitised_user,
            viewers=event.viewers,
            timestamp=event.timestamp
        )
        await self.event_bus.publish(sanitised_event)

    async def _moderate_follow(self, event: TwitchFollowEvent) -> None:
        """Sanitise follow events (mainly the follower username)."""
        sanitised_user = self._sanitise(event.user, default="Someone")

        sanitised_event = TwitchFollowEvent(
            type="twitch_follow_processed",
            data={**event.data, "user": sanitised_user},
            user=sanitised_user,
            followed_at=event.followed_at,
            timestamp=event.timestamp
        )
        await self.event_bus.publish(sanitised_event)

    async def _moderate_kick_chat(self, event: KickChatEvent) -> None:
        """Sanitise kick chat (username + text)."""
        sanitised_user = self._sanitise(event.user, default="Someone")
        sanitised_msg = self._sanitise(event.text, default="")

        sanitised_event = KickChatEvent(
            type="kick_chat_processed",
            data={**event.data, "user": sanitised_user, "text": sanitised_msg},
            user=sanitised_user,
            text=sanitised_msg,
            timestamp=event.timestamp
        )
        await self.event_bus.publish(sanitised_event)

    async def _moderate_kick_subscription(self, event: KickSubscriptionEvent) -> None:
        sanitised_user = self._sanitise(event.user, default="Someone")
        sanitised_msg = self._sanitise(event.sub_message, default="")

        sanitised_event = KickSubscriptionEvent(
            type="kick_subscription_processed",
            data={**event.data, "user": sanitised_user, "sub_message": sanitised_msg},
            user=sanitised_user,
            tier=event.tier,
            sub_type=event.sub_type,
            sub_message=sanitised_msg,
            timestamp=event.timestamp
        )
        await self.event_bus.publish(sanitised_event)

    async def _moderate_kick_raid(self, event: KickRaidEvent) -> None:
        sanitised_user = self._sanitise(event.user, default="Someone")

        sanitised_event = KickRaidEvent(
            type="kick_raid_processed",
            data={**event.data, "user": sanitised_user},
            user=sanitised_user,
            viewers=event.viewers,
            timestamp=event.timestamp
        )
        await self.event_bus.publish(sanitised_event)

    async def _moderate_kick_follow(self, event: KickFollowEvent) -> None:
        sanitised_user = self._sanitise(event.user, default="Someone")

        sanitised_event = KickFollowEvent(
            type="kick_follow_processed",
            data={**event.data, "user": sanitised_user},
            user=sanitised_user,
            followed_at=event.followed_at,
            timestamp=event.timestamp
        )
        await self.event_bus.publish(sanitised_event)

    def _sanitise(self, value: str, default: str = "") -> str:
        """
        Generic sanitizer for usernames or text.
        Returns `default` if `value` contains banned words, otherwise returns `value`.
        """
        return default if contains_banned_words(
            value,
             BLACKLISTED_WORDS_LIST, 
             WHITELISTED_WORDS_LIST
        ) else value
