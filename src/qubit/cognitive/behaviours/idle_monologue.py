"""
IdleMonologueBehavior - scored proposal for autonomous / idle speech.

Goals:
- Fires significantly more at low activity (the "quiet stream" feeling).
- Still allowed to interject occasionally at medium/high activity so the bot
  never feels like a pure reactive Q&A machine.
- After answering a user at low activity, gets a short "follow-up" window so
  the monologue feels like natural conversation instead of abrupt stop/start.
"""

import random

from src.qubit.cognitive.behaviours.base import Behavior
from src.qubit.cognitive.behaviours.topic_selector import TopicSelector
from src.utils.log_utils import get_logger


class IdleMonologueBehavior(Behavior):
    # Activity -> (eagerness, cooldown multiplier applied to BASE_COOLDOWN_SECONDS).
    # Checked in ascending order of ceiling; HIGH_ACTIVITY_* below is the
    # fallback once activity reaches the last ceiling.
    ACTIVITY_TIERS: list[tuple[float, float, float]] = [
        # (activity_ceiling, eagerness, cooldown_multiplier)
        (1.5, 0.88, 0.55),  # ~15s effective cooldown at very low activity
        (3.5, 0.72, 0.75),
        (7.0, 0.38, 1.00),
    ]
    HIGH_ACTIVITY_EAGERNESS = 0.22
    HIGH_ACTIVITY_COOLDOWN_MULT = 1.2

    BASE_COOLDOWN_SECONDS = 28.0

    # Follow-up bonus: right after responding to a human at low activity,
    # briefly boost eagerness so the bot naturally keeps talking instead of
    # going silent — the key anti-"boring" mechanism.
    FOLLOWUP_ACTIVITY_CEILING = 4.5
    FOLLOWUP_RESPONSE_WINDOW_SECONDS = 22.0
    FOLLOWUP_MIN_GAP_SINCE_LAST_SECONDS = 8.0
    FOLLOWUP_EAGERNESS_BONUS = 0.35
    FOLLOWUP_EAGERNESS_CAP = 0.95
    FOLLOWUP_COOLDOWN_CAP_SECONDS = 9.0

    # Soft cooldown gate: even inside the cooldown window, allow a small
    # random "inspiration" chance to fire anyway.
    COOLDOWN_BREACH_CHANCE = 0.07

    # At higher activity, only let a small fraction of ticks through at all,
    # so idle speech feels like an occasional spark, not a habit.
    HIGH_ACTIVITY_SPARK_THRESHOLD = 4.0
    HIGH_ACTIVITY_SPARK_FIRE_CHANCE = 0.17

    ACTIVITY_SCORE_DECAY_RATE = 0.03
    ACTIVITY_SCORE_DECAY_CAP = 0.4
    SCORE_JITTER_RANGE = (-0.04, 0.06)
    SCORE_FLOOR = 0.05
    SCORE_CEILING = 1.35

    def __init__(self):
        super().__init__("IdleMonologue")
        self.logger = get_logger("IdleMonologueBehavior")
        self._selector = TopicSelector()

    async def tick(self, context: dict) -> dict | None:
        if not context.get("features", {}).get("monologue", True):
            return None

        activity = float(context.get("activity_score", 0.0))
        time_since_last = float(context.get("time_since_last_autonomous", 999.0))
        time_since_response = float(context.get("time_since_last_user_response", 999.0))
        catchup = bool(context.get("idle_quota_catchup", False))

        eagerness, effective_cooldown = self._eagerness_for_activity(activity)
        eagerness, effective_cooldown = self._apply_followup_bonus(
            eagerness, effective_cooldown, activity, time_since_response, time_since_last
        )

        # DecisionEngine.IDLE_TARGET_SHARE tracks our actual win rate over
        # time and flags catchup=True when we're under quota. The whole
        # reason we'd be under quota is these two gates suppressing most
        # ticks at higher activity — so during catchup, skip them rather
        # than let the same gates keep us under quota indefinitely.
        if not catchup:
            if not self._passes_cooldown_gate(time_since_last, effective_cooldown):
                return None
            if not self._passes_high_activity_spark_gate(activity):
                return None

        clamped_score = self._final_score(eagerness, activity)
        topic = self._selector.pick(context)

        self.logger.info(
            "[IdleMonologue] PROPOSAL | score=%.3f | activity=%.1f | label=%s | fixed=%s",
            clamped_score, activity, topic.label, topic.is_fixed,
        )

        # Normalized to 0-1: SCORE_CEILING here only bounds this behavior's own
        # internal eagerness math, it no longer encodes priority vs other
        # behaviors — see DecisionEngine.BEHAVIOR_WEIGHTS for that.
        normalized_score = clamped_score / self.SCORE_CEILING

        return {
            "type": "monologue",
            "score": normalized_score,
            "reason": "idle_monologue",
            # The full prompt instruction goes through so the executor can
            # pass it straight to the LLM without constructing it itself.
            "prompt": topic.prompt,
            "label": topic.label,
        }

    def _eagerness_for_activity(self, activity: float) -> tuple[float, float]:
        for ceiling, eagerness, cooldown_mult in self.ACTIVITY_TIERS:
            if activity < ceiling:
                return eagerness, self.BASE_COOLDOWN_SECONDS * cooldown_mult
        return self.HIGH_ACTIVITY_EAGERNESS, self.BASE_COOLDOWN_SECONDS * self.HIGH_ACTIVITY_COOLDOWN_MULT

    def _apply_followup_bonus(
        self,
        eagerness: float,
        effective_cooldown: float,
        activity: float,
        time_since_response: float,
        time_since_last: float,
    ) -> tuple[float, float]:
        eligible = (
            activity < self.FOLLOWUP_ACTIVITY_CEILING
            and time_since_response < self.FOLLOWUP_RESPONSE_WINDOW_SECONDS
            and time_since_last > self.FOLLOWUP_MIN_GAP_SINCE_LAST_SECONDS
        )
        if not eligible:
            return eagerness, effective_cooldown

        boosted_eagerness = min(self.FOLLOWUP_EAGERNESS_CAP, eagerness + self.FOLLOWUP_EAGERNESS_BONUS)
        boosted_cooldown = min(effective_cooldown, self.FOLLOWUP_COOLDOWN_CAP_SECONDS)
        return boosted_eagerness, boosted_cooldown

    def _passes_cooldown_gate(self, time_since_last: float, effective_cooldown: float) -> bool:
        if time_since_last >= effective_cooldown:
            return True
        return random.random() < self.COOLDOWN_BREACH_CHANCE

    def _passes_high_activity_spark_gate(self, activity: float) -> bool:
        if activity < self.HIGH_ACTIVITY_SPARK_THRESHOLD:
            return True
        return random.random() <= self.HIGH_ACTIVITY_SPARK_FIRE_CHANCE

    def _final_score(self, eagerness: float, activity: float) -> float:
        decay = min(self.ACTIVITY_SCORE_DECAY_CAP, activity * self.ACTIVITY_SCORE_DECAY_RATE)
        score = eagerness * (1.0 - decay)
        score += random.uniform(*self.SCORE_JITTER_RANGE)
        return max(self.SCORE_FLOOR, min(self.SCORE_CEILING, score))

