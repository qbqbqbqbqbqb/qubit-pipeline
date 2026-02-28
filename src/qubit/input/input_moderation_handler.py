from src.qubit.utils.log_utils import get_logger
from src.qubit.core.event_bus import event_bus
from config.config import BLACKLISTED_WORDS_LIST, WHITELISTED_WORDS_LIST
from src.qubit.core.events import (
    TwitchChatEvent,
    TwitchSubscriptionEvent,
    TwitchRaidEvent,
    TwitchFollowEvent,
    Event
)
from src.qubit.utils.filter_utils import contains_banned_words

logger = get_logger(__name__)

class ModerationHandler:
    """
    Sole responsibility: filter and sanitize Twitch events.
    Produces sanitized events for downstream consumers.
    """

    async def handle_event(self, event: Event):
        if isinstance(event, TwitchChatEvent):
            await self._moderate_chat(event)
        elif isinstance(event, TwitchSubscriptionEvent):
            await self._moderate_subscription(event)
        elif isinstance(event, TwitchRaidEvent):
            await self._moderate_raid(event)
        elif isinstance(event, TwitchFollowEvent):
            await self._moderate_follow(event)
        else:
            logger.warning(f"[ModerationHandler] Unknown event type: {type(event)}")

    async def _moderate_chat(self, event: TwitchChatEvent):
        sanitized_user = self._sanitize(event.user, default="Someone")
        sanitized_msg =  self._sanitize(event.text, default="")

        sanitized_event = TwitchChatEvent(
            type="twitch_chat_processed",
            data={**event.data, "user": sanitized_user, "text": sanitized_msg},
            user=sanitized_user,
            text=sanitized_msg,
            timestamp=event.timestamp
        )
        await event_bus.publish(sanitized_event)

    async def _moderate_subscription(self, event: TwitchSubscriptionEvent):
        sanitized_user = self._sanitize(event.user, default="Someone")
        sanitized_msg =  self._sanitize(event.sub_message, default="")
        
        sanitized_event = TwitchSubscriptionEvent(
            type="twitch_subscription_processed",
            data={**event.data, "user": sanitized_user, "sub_message": sanitized_msg},
            user=sanitized_user,
            tier=event.tier,
            sub_type=event.sub_type,
            sub_message=event.sub_message,
            timestamp=event.timestamp
        )

        await event_bus.publish(sanitized_event)

    async def _moderate_raid(self, event: TwitchRaidEvent):
        sanitized_user = self._sanitize(event.user, default="Someone")

        sanitized_event = TwitchRaidEvent(
            type="twitch_raid_processed",
            data={**event.data, "user": sanitized_user},
            user=sanitized_user,
            timestamp=event.timestamp
        )
        await event_bus.publish(sanitized_event)

    async def _moderate_follow(self, event: TwitchFollowEvent):
        sanitized_user = self._sanitize(event.user, default="Someone")

        sanitized_event = TwitchFollowEvent(
            type="twitch_follow_processed",
            data={**event.data, "user": sanitized_user},
            user=sanitized_user,
            timestamp=event.timestamp
        )
        await event_bus.publish(sanitized_event)

    def _sanitize(self, value: str, default: str = "") -> str:
        """
        Generic sanitizer for usernames or text.
        Returns `default` if `value` contains banned words, otherwise returns `value`.
        """
        return default if contains_banned_words(value, BLACKLISTED_WORDS_LIST, WHITELISTED_WORDS_LIST) else value