"""
ChatResponseBehavior - scored proposal for responding to chat / STT input.

Design goals:
- STT (live streamer voice) has near-absolute priority at every activity level.
- Low activity: high willingness to answer the few messages that exist.
- High activity: selective — only strong STT + high-quality/mentioned chat survive.
- Cooldown is soft (score penalty), never a hard gate.
"""

from src.qubit.cognitive.behaviours.base import Behavior


class ChatResponseBehavior(Behavior):
    # Activity -> base willingness, checked in ascending order of ceiling.
    # At/above the last ceiling, willingness decays linearly instead
    # (see HIGH_ACTIVITY_* below).
    WILLINGNESS_TIERS: list[tuple[float, float]] = [
        (2.0, 0.92),
        (4.0, 0.78),
        (9.0, 0.55),
    ]
    HIGH_ACTIVITY_BASE = 0.95
    HIGH_ACTIVITY_SELECTIVITY_SLOPE = 0.12  # willingness lost per point of activity above the top tier
    HIGH_ACTIVITY_FLOOR = 0.08

    STT_BOOST_LIVE = 2.8   # applied when the winning message is STT and STT is currently "live"
    STT_BOOST_STALE = 1.6  # applied when the winning message is STT but not flagged live
    WILLINGNESS_CAP = 2.5

    QUALITY_MULT_BASE = 0.6
    QUALITY_MULT_SCALE = 1.1  # quality_mult ends up roughly in the 0.6-1.7 range

    COOLDOWN_SECONDS = 15.0
    COOLDOWN_MIN_PENALTY = 0.25

    SLAMMED_ACTIVITY_THRESHOLD = 9.5
    SLAMMED_QUALITY_FLOOR = 1.1  # below this quality, non-STT proposals are suppressed entirely when slammed

    SCORE_FLOOR = 0.05
    SCORE_CEILING = 3.5

    def __init__(self):
        super().__init__("ChatResponse")

    async def tick(self, context: dict) -> dict | None:
        queue = context["queue"]
        best = queue.get_best()
        if not best:
            return None

        activity = float(context.get("activity_score", 0.0))
        has_live_stt = self._has_live_stt(context, queue)
        is_stt = best.get("source") == "user_input_stt"

        if self._is_suppressed_at_high_activity(activity, is_stt, best.get("quality", 0.5)):
            return None

        willingness = self._base_willingness(context, activity, has_live_stt)
        willingness = self._apply_stt_boost(willingness, is_stt, has_live_stt)
        quality_mult = self._quality_multiplier(best.get("quality", 0.5))
        cooldown_penalty = self._cooldown_penalty(context.get("time_since_last_user_response", 999.0))

        raw_score = willingness * quality_mult * cooldown_penalty
        clamped_score = max(self.SCORE_FLOOR, min(self.SCORE_CEILING, raw_score))

        # Normalized to 0-1: SCORE_CEILING here only bounds this behavior's own
        # internal willingness math, it no longer encodes priority vs other
        # behaviors. DecisionEngine.BEHAVIOR_WEIGHTS is the single place that
        # decides how much a "maxed out" ChatResponse proposal matters relative
        # to a "maxed out" IdleMonologue or FrontendMonologue proposal.
        normalized_score = clamped_score / self.SCORE_CEILING

        return {
            "type": "response",
            "score": normalized_score,
            "reason": "chat_response",
            "priority_tier": 1 if is_stt else 0,
            "best_message": best,
        }

    def _has_live_stt(self, context: dict, queue) -> bool:
        stt_enabled = context.get("features", {}).get("stt", True)
        return queue.has_source("user_input_stt") if stt_enabled else False

    def _base_willingness(self, context: dict, activity: float, has_live_stt: bool) -> float:
        features = context.get("features", {})
        monologue_enabled = features.monologue
        pure_chat_mode = not monologue_enabled and not has_live_stt

        if pure_chat_mode or has_live_stt:
            return 1.0
        return self._willingness_for_activity(activity)

    def _willingness_for_activity(self, activity: float) -> float:
        # Low activity -> more eager to talk to the sparse humans.
        # High activity -> only answer the very best stuff.
        for ceiling, value in self.WILLINGNESS_TIERS:
            if activity < ceiling:
                return value
        top_ceiling = self.WILLINGNESS_TIERS[-1][0]
        return max(
            self.HIGH_ACTIVITY_FLOOR,
            self.HIGH_ACTIVITY_BASE - (activity - top_ceiling) * self.HIGH_ACTIVITY_SELECTIVITY_SLOPE,
        )

    def _apply_stt_boost(self, willingness: float, is_stt: bool, has_live_stt: bool) -> float:
        if not is_stt:
            return willingness
        boost = self.STT_BOOST_LIVE if has_live_stt else self.STT_BOOST_STALE
        return min(self.WILLINGNESS_CAP, willingness * boost)

    def _quality_multiplier(self, quality: float) -> float:
        return self.QUALITY_MULT_BASE + (quality * self.QUALITY_MULT_SCALE)

    def _cooldown_penalty(self, time_since_response: float) -> float:
        if time_since_response >= self.COOLDOWN_SECONDS:
            return 1.0
        # Linear penalty from 1.0 down to COOLDOWN_MIN_PENALTY over the cooldown window.
        return max(
            self.COOLDOWN_MIN_PENALTY,
            1.0 - (self.COOLDOWN_SECONDS - time_since_response) / self.COOLDOWN_SECONDS,
        )

    def _is_suppressed_at_high_activity(self, activity: float, is_stt: bool, quality: float) -> bool:
        if activity <= self.SLAMMED_ACTIVITY_THRESHOLD or is_stt:
            return False
        # Only let high-quality mentions/questions through when slammed.
        return quality < self.SLAMMED_QUALITY_FLOOR