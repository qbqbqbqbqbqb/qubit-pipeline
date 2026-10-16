"""
<summary>
IdleQuotaTracker — keeps idle_monologue's share of decisions near a target ratio over time.
</summary>
<remarks>
Tracks the last N chat-vs-monologue outcomes and signals "catch-up" — a decisive score
bonus plus (via context) letting IdleMonologueBehavior bypass its random gates — whenever
the trailing share drops below the target. Once back at or above target, catch-up switches
off and idle returns to its normal eagerness curves.

A purely multiplicative correction does not converge to the target because a bounded
multiplier cannot close the large score-magnitude gap between idle's ceiling and chat's
floor at high activity. Only a guaranteed win during catch-up reliably converges.
</remarks>
"""

from collections import deque


class IdleQuotaTracker:
    """
    <summary>
    Sliding-window tracker for the idle-monologue-to-chat-response ratio.
    Signals catch-up when the trailing share falls below TARGET_SHARE.
    </summary>
    """

    TARGET_SHARE = 0.30
    HISTORY_SIZE = 20
    MIN_SAMPLES = 5
    CATCHUP_BONUS = 5.0  # far exceeds any realistic tier-0 weighted score — guarantees the win

    REASON = "idle_monologue"
    COMPETING_REASON = "chat_response"

    def __init__(self):
        self._history: deque[str] = deque(maxlen=self.HISTORY_SIZE)

    def is_under_quota(self) -> bool:
        """
        <summary>
        Return True if the idle-monologue share in recent history is below TARGET_SHARE
        and enough samples exist to make the assessment meaningful.
        </summary>
        <returns>True when catch-up mode should activate.</returns>
        """
        relevant = [d for d in self._history if d in ("response", "monologue")]
        if len(relevant) < self.MIN_SAMPLES:
            return False
        share = relevant.count("monologue") / len(relevant)
        return share < self.TARGET_SHARE

    def catchup_bonus(self, under_quota: bool) -> float:
        """
        <summary>Return the catch-up score bonus for this cycle.</summary>
        <param name="under_quota">The result of is_under_quota() for this cycle.</param>
        <returns>CATCHUP_BONUS when under quota, 0.0 otherwise.</returns>
        """
        return self.CATCHUP_BONUS if under_quota else 0.0

    def record(self, reason: str) -> None:
        """
        <summary>
        Record an outcome in the history window. Only chat_response and idle_monologue
        are tracked — frontend commands and community events are excluded from the ratio.
        </summary>
        <param name="reason">The reason string from the winning proposal.</param>
        """
        if reason == self.COMPETING_REASON:
            self._history.append("response")
        elif reason == self.REASON:
            self._history.append("monologue")
