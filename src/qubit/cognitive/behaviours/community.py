"""
CommunityEventBehavior - scored proposal for raids, gifted subs, and follows.

These are rarer than an ordinary chat message and far rarer than routine
STT, so they always take priority over both chat and monologue, and also
over live STT — see DecisionEngine.PRIORITY_TIER_BONUS and this behavior's
PRIORITY_TIER.

If more than one event is pending when this behavior ticks (e.g. several
gifted subs land in the same window), they're collated into a single
acknowledgement instead of firing one response per event. There's no
explicit "is this spam" detection — it simply reacts to whatever is
currently pending, so a burst that lands within one decision cycle is
naturally batched, and a lone event just gets a collation of one.
"""

from src.qubit.cognitive.behaviours.base import Behavior
from src.qubit.utils.log_utils import get_logger


class CommunityEventBehavior(Behavior):
    # Always wins against chat/idle/frontend, and against live STT — see
    # DecisionEngine.PRIORITY_TIER_BONUS. The exact NORMALIZED_SCORE/weight
    # barely matters once the tier bonus is added; kept at max (1.0) since
    # a raid or gift genuinely warrants this behavior's full enthusiasm.
    PRIORITY_TIER = 2
    NORMALIZED_SCORE = 1.0

    def __init__(self):
        super().__init__("CommunityEvent")
        self.logger = get_logger("CommunityEventBehavior")

    async def tick(self, context: dict) -> dict | None:
        events = context.get("pending_events") or []
        if not events:
            return None

        topic = self._collate(events)

        self.logger.info("[CommunityEvent] PROPOSAL | count=%d | topic=%s", len(events), topic)

        return {
            "type": "community_event",
            "score": self.NORMALIZED_SCORE,
            "reason": "community_event",
            "priority_tier": self.PRIORITY_TIER,
            "topic": topic,
            "events": events,  # snapshot — DecisionEngine removes exactly these on execution
        }

    def _collate(self, events: list[dict]) -> str:
        if len(events) == 1:
            return self._describe(events[0])
        descriptions = [self._describe(e) for e in events]
        return "several community events at once: " + "; ".join(descriptions)

    def _describe(self, event: dict) -> str:
        """
        event dicts come from ActivityTracker._extract_event_detail(), built
        from the real TwitchRaidEvent/TwitchSubscriptionEvent (and Kick
        equivalents) fields: raids carry viewer_count, subs carry tier and
        sub_type. There's no numeric gift count in the schema — a gift is a
        subscription whose sub_type is a gift value (see
        ActivityTracker.GIFT_SUB_TYPES), so it's described qualitatively,
        not "X gifted 3 subs".
        """
        kind = event.get("kind")
        username = event.get("username", "someone")

        if kind == "raid":
            viewers = event.get("viewer_count")
            return f"a raid from {username} with {viewers} viewers" if viewers else f"a raid from {username}"

        if kind == "subscription":
            return self._describe_subscription(username, event.get("sub_type"), event.get("tier"))

        if kind == "follow":
            return f"a follow from {username}"

        return f"an event from {username}"

    def _describe_subscription(self, username: str, sub_type: str | None, tier: str | None) -> str:
        tier_suffix = f" ({tier})" if tier else ""
        if (sub_type or "").lower() == "gift":
            return f"{username} gifting a sub{tier_suffix}"
        return f"{username} subscribing{tier_suffix}"