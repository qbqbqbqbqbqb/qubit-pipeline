"""
<summary>
CommunityEventBehavior — scored proposal for raids, gifted subs, and follows.
</summary>
<remarks>
Community events are rarer than chat messages and always take priority over chat,
monologue, and live STT — see ProposalArbiter.PRIORITY_TIER_BONUS and PRIORITY_TIER.

Multiple pending events within one decision cycle are collated into a single
acknowledgement rather than firing one response per event. A lone event produces
a collation of one.
</remarks>
"""

from src.qubit.cognitive.behaviours.base import Behavior
from src.qubit.utils.log_utils import get_logger


class CommunityEventBehavior(Behavior):
    """
    <summary>
    Proposes a community event reaction when one or more pending events are queued.
    Always wins against chat, idle, and frontend behaviours due to its priority tier.
    </summary>
    """

    PRIORITY_TIER = 2
    NORMALIZED_SCORE = 1.0

    def __init__(self):
        super().__init__("CommunityEvent")
        self.logger = get_logger("CommunityEventBehavior")

    async def tick(self, context: dict) -> dict | None:
        """
        <summary>
        Propose a community event reaction if any events are pending.
        Multiple events are collated into a single topic string.
        </summary>
        <param name="context">The cycle context dict from DecisionEngine.</param>
        <returns>A community_event proposal dict, or None if nothing is pending.</returns>
        """
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
            "events": events,
        }

    def _collate(self, events: list[dict]) -> str:
        if len(events) == 1:
            return self._describe(events[0])
        descriptions = [self._describe(e) for e in events]
        return "several community events at once: " + "; ".join(descriptions)

    def _describe(self, event: dict) -> str:
        """
        <summary>
        Produce a human-readable description of a single community event detail dict.
        Raid events carry viewer_count; subscription events carry tier and sub_type.
        </summary>
        <param name="event">An event detail dict from ActivityTracker.</param>
        <returns>A descriptive string for use in the reaction prompt topic.</returns>
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
