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

Dispatch table:
  Each entry in _EVENT_SPECS maps an event class to a (output_type,
  sanitised_fields) descriptor. sanitised_fields is an ordered list of
  (field_name, default) pairs. A default of None means: drop the event
  entirely if the field is banned rather than substituting a value.
</remarks>
"""

import dataclasses
from typing import Any

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
    Event,
)
from src.qubit.utils.filter_utils import contains_banned_words


# ---------------------------------------------------------------------------
# Dispatch table
#
# Maps each raw event class to:
#   output_type      — the type string written onto the published event
#   sanitised_fields — list of (field_name, default) pairs to run through
#                      _sanitise().  default=None means drop the event when
#                      the field is banned (used for message text).
# ---------------------------------------------------------------------------
_EVENT_SPECS: dict[type, tuple[str, list[tuple[str, Any]]]] = {
    TwitchChatEvent: (
        "twitch_chat_processed",
        [("user", "Someone"), ("text", None)],
    ),
    TwitchSubscriptionEvent: (
        "twitch_subscription_processed",
        [("user", "Someone"), ("sub_message", "")],
    ),
    TwitchRaidEvent: (
        "twitch_raid_processed",
        [("user", "Someone")],
    ),
    TwitchFollowEvent: (
        "twitch_follow_processed",
        [("user", "Someone")],
    ),
    KickChatEvent: (
        "kick_chat_processed",
        [("user", "Someone"), ("text", None)],
    ),
    KickSubscriptionEvent: (
        "kick_subscription_processed",
        [("user", "Someone"), ("sub_message", "")],
    ),
    KickRaidEvent: (
        "kick_raid_processed",
        [("user", "Someone")],
    ),
    KickFollowEvent: (
        "kick_follow_processed",
        [("user", "Someone")],
    ),
}


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
        Entry point for all raw platform events. Looks up the event class in
        _EVENT_SPECS, sanitises the declared fields, and publishes a clean
        *_processed variant. Drops the event silently if any field with
        default=None is banned, or if the event class is unknown.
        </summary>
        <param name="event">The raw platform event from the bus.</param>
        """
        spec = _EVENT_SPECS.get(type(event))
        if spec is None:
            self.logger.warning("[handle_event] Unknown event type: %s", event.type)
            return

        output_type, sanitised_fields = spec
        await self._moderate(event, output_type, sanitised_fields)

    async def _moderate(
        self,
        event: Event,
        output_type: str,
        sanitised_fields: list[tuple[str, Any]],
    ) -> None:
        """
        <summary>
        Sanitise the declared fields, build a clean copy of the event with the
        output type, and publish it. Drops the event if any field whose default
        is None comes back banned.
        </summary>
        <param name="event">The raw event to sanitise.</param>
        <param name="output_type">The type string for the published event.</param>
        <param name="sanitised_fields">
            Ordered list of (field_name, default) pairs. default=None means
            drop the event when that field is banned.
        </param>
        """
        overrides: dict[str, Any] = {}

        for field_name, default in sanitised_fields:
            raw_value = getattr(event, field_name, None)
            clean = self._sanitise(raw_value, default=default)
            if clean is None:
                self.logger.debug(
                    "[_moderate] Dropping event %s — banned content in field '%s'",
                    output_type, field_name,
                )
                return
            overrides[field_name] = clean

        updated_data = {**event.data, **overrides}
        sanitised_event = dataclasses.replace(
            event,
            type=output_type,
            data=updated_data,
            **overrides,
        )
        await self.event_bus.publish(sanitised_event)

    def _sanitise(self, value: str | None, default: Any = "") -> Any:
        """
        <summary>
        Return default if value is None or contains banned words, otherwise
        return value unchanged. A default of None signals drop-on-ban to the
        caller rather than substitution.
        </summary>
        <param name="value">The string to check (username or message text).</param>
        <param name="default">Value to return when banned content is detected.</param>
        <returns>The sanitised string or the default.</returns>
        """
        if value is None:
            return default
        return default if contains_banned_words(
            value,
            BLACKLISTED_WORDS_LIST,
            WHITELISTED_WORDS_LIST,
        ) else value
