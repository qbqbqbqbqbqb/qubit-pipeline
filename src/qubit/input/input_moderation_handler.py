# dont know whether to keep this as a service without a main loop
# might be cleaner to leave as is?
from src.qubit.core.service import Service
from config.config import BLACKLISTED_WORDS_LIST, WHITELISTED_WORDS_LIST
from src.qubit.core.events import (
    TwitchChatEvent,
    TwitchSubscriptionEvent,
    TwitchRaidEvent,
    TwitchFollowEvent,
    Event
)
from src.qubit.utils.filter_utils import contains_banned_words

class ModerationHandler(Service):
    
    """
    Sole responsibility: filter and sanitize Twitch events.
    Produces sanitized events for downstream consumers.
    """
    SUBSCRIPTIONS = {
        "twitch_chat": "handle_event",
        "twitch_subscription": "handle_event",
        "twitch_raid": "handle_event",
        "twitch_follow": "handle_event",
    }

    def __init__(self):
        super().__init__("input moderation handler")

    async def start(self, app) -> None:
        await super().start(app)

    async def stop(self) -> None:
        await super().stop()

    async def handle_event(self, event: Event) -> None:
        if isinstance(event, TwitchChatEvent):
            self.logger.info("moderating twitch chat event")
            await self._moderate_chat(event)
        elif isinstance(event, TwitchSubscriptionEvent):
            await self._moderate_subscription(event)
        elif isinstance(event, TwitchRaidEvent):
            await self._moderate_raid(event)
        elif isinstance(event, TwitchFollowEvent):
            await self._moderate_follow(event)
        else:
            self.logger.warning(f"[ModerationHandler] Unknown event type: {type(event)}")

    async def _moderate_chat(self, event: TwitchChatEvent) -> None:
        sanitised_user = self._sanitise(event.user, default="Someone")
        sanitised_msg =  self._sanitise(event.text, default="")

        sanitised_event = TwitchChatEvent(
            type="twitch_chat_processed",
            data={**event.data, "user": sanitised_user, "text": sanitised_msg},
            user=sanitised_user,
            text=sanitised_msg,
            timestamp=event.timestamp
        )
        await self.event_bus.publish(sanitised_event)

    async def _moderate_subscription(self, event: TwitchSubscriptionEvent) -> None:
        sanitised_user = self._sanitise(event.user, default="Someone")
        sanitised_msg =  self._sanitise(event.sub_message, default="")
        
        sanitised_event = TwitchSubscriptionEvent(
            type="twitch_subscription_processed",
            data={**event.data, "user": sanitised_user, "sub_message": sanitised_msg},
            user=sanitised_user,
            tier=event.tier,
            sub_type=event.sub_type,
            sub_message=event.sub_message,
            timestamp=event.timestamp
        )

        await self.event_bus.publish(sanitised_event)

    async def _moderate_raid(self, event: TwitchRaidEvent) -> None:
        sanitised_user = self._sanitise(event.user, default="Someone")

        sanitised_event = TwitchRaidEvent(
            type="twitch_raid_processed",
            data={**event.data, "user": sanitised_user},
            user=sanitised_user,
            timestamp=event.timestamp
        )
        await self.event_bus.publish(sanitised_event)

    async def _moderate_follow(self, event: TwitchFollowEvent) -> None:
        sanitised_user = self._sanitise(event.user, default="Someone")

        sanitised_event = TwitchFollowEvent(
            type="twitch_follow_processed",
            data={**event.data, "user": sanitised_user},
            user=sanitised_user,
            timestamp=event.timestamp
        )
        await self.event_bus.publish(sanitised_event)

    def _sanitise(self, value: str, default: str = "") -> str:
        """
        Generic sanitizer for usernames or text.
        Returns `default` if `value` contains banned words, otherwise returns `value`.
        """
        return default if contains_banned_words(value, BLACKLISTED_WORDS_LIST, WHITELISTED_WORDS_LIST) else value