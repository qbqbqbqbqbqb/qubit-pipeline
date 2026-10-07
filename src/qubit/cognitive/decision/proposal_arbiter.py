"""
ProposalArbiter - decides which of a cycle's scored proposals wins.

Owns BEHAVIOR_WEIGHTS (inter-behavior priority for normal, tier-0
competition) and PRIORITY_TIER_BONUS (priority classes that override
weights entirely — live STT, community events). Tuning "how much do
behaviors compete with each other" lives here, not scattered across
behavior files or mixed into DecisionEngine's cycle-sequencing logic.

Each behavior returns a proposal score normalized to roughly 0-1 — "how
much do I want this, on my own internal scale." This class is what decides
how much a maxed-out proposal from one behavior matters relative to
another; a behavior's own SCORE_FLOOR/SCORE_CEILING never leaks out to
decide priority against other behaviors.

Priority tiers, on top of weighted score:
    tier 0: chat_response (non-STT), idle_monologue, frontend_*
    tier 1: chat_response when the winning message is live STT
    tier 2: community_event (raids/gifts/follows) — always wins, even over STT
"""


class ProposalArbiter:
    BEHAVIOR_WEIGHTS: dict[str, float] = {
        "chat_response": 1.0,
        "frontend_start": 0.75,
        "frontend_random_fact": 0.75,
        "idle_monologue": 0.4,
        "community_event": 1.0,
    }
    DEFAULT_BEHAVIOR_WEIGHT = 0.4
    PRIORITY_TIER_BONUS = 10.0

    def select_winner(
        self,
        proposals: list[dict],
        extra_bonus_by_reason: dict[str, float] | None = None,
    ) -> dict:
        """
        extra_bonus_by_reason lets a caller inject a one-off additive bonus
        for a specific behavior's "reason" this cycle (e.g. DecisionEngine
        passing IdleQuotaTracker's catch-up bonus for "idle_monologue") —
        this class doesn't need to know why, just that it should be added.
        """
        extra_bonus_by_reason = extra_bonus_by_reason or {}

        def proposal_key(p: dict) -> float:
            reason = p.get("reason")
            weight = self.BEHAVIOR_WEIGHTS.get(reason, self.DEFAULT_BEHAVIOR_WEIGHT)
            score = p.get("score", 0.0) * weight
            score += p.get("priority_tier", 0) * self.PRIORITY_TIER_BONUS
            score += extra_bonus_by_reason.get(reason, 0.0)
            return score

        return max(proposals, key=proposal_key)