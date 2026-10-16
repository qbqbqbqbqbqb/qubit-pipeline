"""
<summary>
ModerationProcessor — first-pass input filter for all Twitch and Kick events.
</summary>
<remarks>
LAYER: Input Processing

Receives raw platform events (chat, subscriptions, raids, follows) and produces
sanitised *_processed events for downstream layers. Acts as a gatekeeper: any
event that passes through is considered safe for memory storage and for feeding
into the decision engine.

Responsibilities:
  - Detect and filter banned words using shared filter utilities.
  - Sanitise usernames and message text.
  - Emit clean *_processed events rather than mutating the originals.

This processor is intentionally narrow. It does not make decisions about
whether to respond — that belongs in the Cognitive layer.
</remarks>
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
    <summary>
    Pure EventProcessor that sanitises raw platform input events before they
    propagate to the Cognitive and Memory layers.
    </summary>
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
        <summary>
        Entry point for all raw platform events. Dispatches to the appropriate
        moderation method based on event type and publishes a clean *_processed variant.
        </summary>
        <param name="event">The raw platform event from the bus.</param>
        """
        if isinstance(event, TwitchChatEvent):
            self.logger.debug("[handle_event] Moderating twitch chat event: %s", event)
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
            self.logger.debug("[handle_event] Moderating kick chat event: %s", event)
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
        """
        <summary>
        Sanitise username and message text, then publish a clean processed event.
        Drops the event entirely if the message text is blacklisted.
        </summary>
        <param name="event">The raw TwitchChatEvent.</param>
        """
        sanitised_user = self._sanitise(event.user, default="Someone")
        sanitised_msg = self._sanitise(event.text, default=None)

        if not sanitised_msg:
            self.logger.debug("[_moderate_chat] Dropping blacklisted message from %s", sanitised_user)
            return

        sanitised_event = TwitchChatEvent(
            type="twitch_chat_processed",
            data={**event.data, "user": sanitised_user, "text": sanitised_msg},
            user=sanitised_user,
            text=sanitised_msg,
            timestamp=event.timestamp,
        )
        await self.event_bus.publish(sanitised_event)

    async def _moderate_subscription(self, event: TwitchSubscriptionEvent) -> None:
        """
        <summary>Sanitise subscription events (user and optional sub message).</summary>
        <param name="event">The raw TwitchSubscriptionEvent.</param>
        """
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
        """
        <summary>Sanitise raid events (mainly the raider username).</summary>
        <param name="event">The raw TwitchRaidEvent.</param>
        """
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
        """
        <summary>Sanitise follow events (mainly the follower username).</summary>
        <param name="event">The raw TwitchFollowEvent.</param>
        """
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
        """
        <summary>Sanitise Kick chat events (username and text). Drops event if text is blacklisted.</summary>
        <param name="event">The raw KickChatEvent.</param>
        """
        sanitised_user = self._sanitise(event.user, default="Someone")
        sanitised_msg = self._sanitise(event.text, default=None)

        if not sanitised_msg:
            self.logger.debug("[_moderate_kick_chat] Dropping blacklisted message from %s", sanitised_user)
            return

        sanitised_event = KickChatEvent(
            type="kick_chat_processed",
            data={**event.data, "user": sanitised_user, "text": sanitised_msg},
            user=sanitised_user,
            text=sanitised_msg,
            timestamp=event.timestamp,
        )
        await self.event_bus.publish(sanitised_event)

    async def _moderate_kick_subscription(self, event: KickSubscriptionEvent) -> None:
        """
        <summary>Sanitise Kick subscription events (user and optional sub message).</summary>
        <param name="event">The raw KickSubscriptionEvent.</param>
        """
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
        """
        <summary>Sanitise Kick raid events (mainly the raider username).</summary>
        <param name="event">The raw KickRaidEvent.</param>
        """
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
        """
        <summary>Sanitise Kick follow events (mainly the follower username).</summary>
        <param name="event">The raw KickFollowEvent.</param>
        """
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
        <summary>
        Return default if value contains banned words, otherwise return value unchanged.
        </summary>
        <param name="value">The string to check (username or message text).</param>
        <param name="default">Value to return when banned content is detected.</param>
        <returns>The sanitised string or the default.</returns>
        """
        return default if contains_banned_words(
            value,
            BLACKLISTED_WORDS_LIST,
            WHITELISTED_WORDS_LIST
        ) else value
