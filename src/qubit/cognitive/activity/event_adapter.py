"""
<summary>
EventAdapter — translates raw pipeline Event objects into the canonical shapes
that ActivityTracker and its collaborators work with.
</summary>
<remarks>
Isolated here because this is the piece most likely to break when Input
Processing's event schema changes. It is testable against fake event objects
without touching ActivityTracker's state at all.

Community events (raids, subscriptions, follows) use the *_processed naming
convention because they arrive after ModerationProcessor, which sanitises
usernames before forwarding them downstream.
</remarks>
"""


class EventAdapter:
    """
    <summary>
    Stateless adapter that maps Event objects to the canonical source strings,
    feature flags, text fields, and detail dicts that ActivityTracker expects.
    </summary>
    """

    # Event type -> canonical source string used for weighting and queuing.
    # Community events map to their own source strings so ActivityTracker
    # routes them to CommunityEventQueue rather than the text priority queue.
    SOURCE_BY_EVENT_TYPE = {
        "stt_processed": "user_input_stt",
        "twitch_chat_processed": "user_input_chat_message",
        "kick_chat_processed": "user_input_chat_message",
        "twitch_raid_processed": "user_event_raid",
        "twitch_subscription_processed": "user_event_subscription",
        "twitch_follow_processed": "user_event_follow",
        "kick_raid_processed": "user_event_raid",
        "kick_subscription_processed": "user_event_subscription",
        "kick_follow_processed": "user_event_follow",
    }
    DEFAULT_SOURCE = "other"

    # Source -> feature flag that must be True for this input to be processed.
    # user_event_subscription is absent here — feature_flag_for() splits gift
    # vs non-gift subs by inspecting sub_type, since the schema has no separate
    # gift event type to route on.
    # Follows are bundled under the 'raids' toggle by default.
    FEATURE_FLAG_BY_SOURCE = {
        "user_input_stt": "stt",
        "user_input_chat_message": "chat",
        "user_event_raid": "raids",
        "user_event_follow": "raids",
    }

    # sub_type values that count as a gift for the purposes of the gifts toggle.
    GIFT_SUB_TYPES = {"gift"}

    # Sources routed to CommunityEventQueue instead of the text priority queue.
    EVENT_SOURCES = {"user_event_raid", "user_event_subscription", "user_event_follow"}

    @classmethod
    def get_source(cls, event) -> str:
        """
        <summary>Map an event's type to a canonical source string.</summary>
        <param name="event">The Event instance to inspect.</param>
        <returns>A canonical source string such as 'user_input_stt'.</returns>
        """
        return cls.SOURCE_BY_EVENT_TYPE.get(event.type, cls.DEFAULT_SOURCE)

    @classmethod
    def feature_flag_for(cls, source: str, event) -> str | None:
        """
        <summary>
        Resolve which feature flag gates this input. Subscriptions are split by
        sub_type since there is no separate gift event type in the schema.
        </summary>
        <param name="source">Canonical source string for the event.</param>
        <param name="event">The Event instance, inspected for sub_type when needed.</param>
        <returns>The feature flag name string, or None if no flag applies.</returns>
        """
        if source == "user_event_subscription":
            sub_type = getattr(event, "sub_type", None)
            if sub_type is None and hasattr(event, "data"):
                sub_type = event.data.get("sub_type")
            if (sub_type or "").lower() in cls.GIFT_SUB_TYPES:
                return "gifts"
            return "raids"
        return cls.FEATURE_FLAG_BY_SOURCE.get(source)

    @classmethod
    def extract_text(cls, event) -> str:
        """
        <summary>
        Extract the text payload from a chat or STT event. TwitchChatEvent,
        KickChatEvent, and SpeechEvent all carry 'text' as a direct dataclass
        field; generic Events fall back to data.get('text').
        </summary>
        <param name="event">The Event instance to extract text from.</param>
        <returns>The text string, or an empty string if not present.</returns>
        """
        text = getattr(event, "text", None)
        if text is not None:
            return text
        if hasattr(event, "data"):
            return event.data.get("text", "")
        return ""

    @classmethod
    def extract_event_detail(cls, event, source: str) -> dict:
        """
        <summary>
        Build a detail dict for a community event using the field names defined
        in the core Event dataclasses.
        </summary>
        <remarks>
        Field names match the real dataclasses in core/events.py:
          TwitchRaidEvent/KickRaidEvent        -> user, viewers
          TwitchSubscriptionEvent/KickSub...   -> user, tier, sub_type, sub_message
          TwitchFollowEvent/KickFollowEvent    -> user, followed_at
        There is no numeric gift count in the schema; gifting is represented
        by sub_type alone.
        </remarks>
        <param name="event">The Event instance to extract detail from.</param>
        <param name="source">Canonical source string identifying the event kind.</param>
        <returns>A detail dict suitable for CommunityEventQueue.add().</returns>
        """
        username = getattr(event, "user", None)
        if username is None and hasattr(event, "data"):
            username = event.data.get("user")
        username = username or "someone"

        if source == "user_event_raid":
            viewers = getattr(event, "viewers", None)
            if viewers is None and hasattr(event, "data"):
                viewers = event.data.get("viewers")
            return {"kind": "raid", "username": username, "viewer_count": viewers}

        if source == "user_event_subscription":
            tier = getattr(event, "tier", None)
            sub_type = getattr(event, "sub_type", None)
            if hasattr(event, "data"):
                tier = tier or event.data.get("tier")
                sub_type = sub_type or event.data.get("sub_type")
            return {"kind": "subscription", "username": username, "tier": tier, "sub_type": sub_type}

        if source == "user_event_follow":
            return {"kind": "follow", "username": username}

        return {"kind": "other", "username": username}
