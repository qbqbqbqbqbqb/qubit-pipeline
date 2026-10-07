"""
IdleQuotaTracker - keeps idle_monologue's share of chat-vs-monologue
decisions near a target ratio over time.

Left alone, idle monologue's own eagerness curve gets crushed at high chat
activity (see behaviours/idle_monologue.py's spark gate). This tracks the
last N chat-vs-monologue outcomes and signals "catch-up" — a decisive score
bonus, plus (via context) letting IdleMonologueBehavior bypass its own
random gates — whenever the trailing share drops below target. Once back
at/above target, catch-up switches off and idle goes back to behaving
exactly as its own curves define.

A softer, purely multiplicative correction was tried first and verified (by
simulation) to NOT reach target — it settles into a permanent steady-state
deficit, because a bounded multiplier can't close the large score-magnitude
gap between idle's ceiling and chat's floor at high activity. Only a
guaranteed win during catch-up actually converges.
"""

from collections import deque


class IdleQuotaTracker:
    TARGET_SHARE = 0.30
    HISTORY_SIZE = 20
    MIN_SAMPLES = 5
    CATCHUP_BONUS = 5.0  # far exceeds any realistic tier-0 weighted score — guarantees the win

    REASON = "idle_monologue"
    COMPETING_REASON = "chat_response"

    def __init__(self):
        self._history: deque[str] = deque(maxlen=self.HISTORY_SIZE)

    def is_under_quota(self) -> bool:
        relevant = [d for d in self._history if d in ("response", "monologue")]
        if len(relevant) < self.MIN_SAMPLES:
            return False  # not enough history yet — let normal behavior run first
        share = relevant.count("monologue") / len(relevant)
        return share < self.TARGET_SHARE

    def catchup_bonus(self) -> float:
        return self.CATCHUP_BONUS if self.is_under_quota() else 0.0

    def record(self, reason: str) -> None:
        # Only chat_response vs idle_monologue feed the ratio — frontend
        # commands are deliberate operator overrides and community events
        # are rare reactions; neither belongs in an emergent "how much does
        # she talk on her own vs. respond" measurement.
        if reason == self.COMPETING_REASON:
            self._history.append("response")
        elif reason == self.REASON:
            self._history.append("monologue")