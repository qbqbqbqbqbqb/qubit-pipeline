"""
EventAdapter - translates raw pipeline Event objects into the canonical
shapes ActivityTracker and its collaborators work with.

"""


class EventAdapter:
    SOURCE_BY_EVENT_TYPE = {
        "stt_processed": "user_input_stt",
        "twitch_chat_processed": "user_input_chat_message",
        "kick_chat_processed": "user_input_chat_message",
        "user_event_follow": "user_event_follow",
        "user_event_subscription": "user_event_subscription",
        "user_event_raid": "user_event_raid",
    }
    DEFAULT_SOURCE = "other"

    FEATURE_FLAG_BY_SOURCE = {
        "user_input_stt": "stt",
        "user_input_chat_message": "chat",
        "user_event_raid": "raids",
        "user_event_follow": "raids",
    }
    GIFT_SUB_TYPES = {"gift"}

    EVENT_SOURCES = {"user_event_raid", "user_event_subscription", "user_event_follow"}

    @classmethod
    def get_source(cls, event) -> str:
        """Map event type to a canonical source string used for weighting and queuing."""
        return cls.SOURCE_BY_EVENT_TYPE.get(event.type, cls.DEFAULT_SOURCE)

    @classmethod
    def feature_flag_for(cls, source: str, event) -> str | None:
        """
        Resolve which feature flag gates this input. Subscriptions are split
        by sub_type since there's no separate "gift" event type in the
        schema — TwitchSubscriptionEvent/KickSubscriptionEvent both carry a
        sub_type field that a gift shows up as (see GIFT_SUB_TYPES).
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
        TwitchChatEvent/KickChatEvent/SpeechEvent all carry `text` as a
        direct dataclass field, not inside `.data` — try that first. Falls
        back to `.data.get("text")` for any event shaped as a generic Event
        with the payload only in the dict.
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
        Field names match the real dataclasses in core/events.py:
        TwitchRaidEvent/KickRaidEvent -> user, viewers (direct attributes).
        TwitchSubscriptionEvent/KickSubscriptionEvent -> user, tier,
        sub_type, sub_message (direct attributes) — there's no numeric gift
        count in the schema, so gifting is represented by sub_type alone.
        TwitchFollowEvent/KickFollowEvent -> user, followed_at.
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