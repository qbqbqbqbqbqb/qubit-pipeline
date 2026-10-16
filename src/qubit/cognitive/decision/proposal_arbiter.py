"""
<summary>
ProposalArbiter — decides which of a cycle's scored proposals wins.
</summary>
<remarks>
Owns BEHAVIOR_WEIGHTS (inter-behavior priority for normal tier-0 competition) and
PRIORITY_TIER_BONUS (priority classes that override weights for live STT and community
events). Tuning "how much do behaviours compete with each other" belongs here, not
scattered across behaviour files or mixed into DecisionEngine's cycle-sequencing logic.

Each behaviour normalises its proposal score to roughly 0–1 on its own internal scale.
This class decides how much a maxed-out proposal from one behaviour matters relative
to another.

Priority tiers, applied on top of weighted score:
  tier 0: chat_response (non-STT), idle_monologue, frontend_*
  tier 1: chat_response when the winning message is live STT
  tier 2: community_event (raids/gifts/follows) — always wins, even over live STT
</remarks>
"""


class ProposalArbiter:
    """
    <summary>
    Selects the winning proposal from a cycle by applying behaviour weights,
    priority tier bonuses, and any caller-supplied one-off bonuses.
    </summary>
    """

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
        <summary>
        Select the highest-scoring proposal after applying weights, tier bonuses,
        and any caller-supplied per-reason bonuses.
        </summary>
        <param name="proposals">All proposals collected from enabled behaviours this cycle.</param>
        <param name="extra_bonus_by_reason">
        Optional one-off additive bonus keyed by reason string (e.g. IdleQuotaTracker's
        catch-up bonus for 'idle_monologue'). This class does not need to know why —
        it just adds it.
        </param>
        <returns>The proposal dict with the highest composite score.</returns>
        """
        extra_bonus_by_reason = extra_bonus_by_reason or {}

        def proposal_key(p: dict) -> float:
            reason = p.get("reason")
            weight = self.BEHAVIOR_WEIGHTS.get(reason, self.DEFAULT_BEHAVIOR_WEIGHT)
            score = p.get("score", 0.0) * weight
            score += p.get("priority_tier", 0) * self.PRIORITY_TIER_BONUS
            score += extra_bonus_by_reason.get(reason, 0.0)
            return score

        valid = [p for p in proposals if p is not None]
        if not valid:
            return None
        return max(valid, key=proposal_key)
