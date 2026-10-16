"""
<summary>
ActivityScore — the chat-only "how busy is chat" scalar used by the cognitive layer.
</summary>
<remarks>
Driven exclusively by written chat messages. STT and community events (raids/gifts/follows)
do not contribute to this score — they win through DecisionEngine's priority tiers,
independent of chat busyness.
</remarks>
"""

from datetime import datetime, timezone


class ActivityScore:
    """
    <summary>
    Tracks a rolling chat busyness value that rises on each incoming message
    and decays over time when chat goes quiet.
    </summary>
    """

    MAX_ACTIVITY_SCORE = 15.0
    CHAT_WEIGHT = 1.0
    MONOLOGUE_DISABLED_MULTIPLIER = 0.3
    DECAY_FACTOR = 0.85

    # Expected cadence for apply_time_decay() calls. Decay is computed from actual
    # elapsed wall-clock time so correctness is maintained if the cadence drifts.
    DECAY_INTERVAL_SECONDS = 5.0

    def __init__(self):
        self.value = 0.0
        self.last_activity = datetime.now(timezone.utc)
        self._last_decay_time = datetime.now(timezone.utc)

    def register_chat_message(self, features) -> None:
        """
        <summary>Bump the score for one incoming chat message.</summary>
        <param name="features">Current FeatureFlags, used to scale weight when monologue is disabled.</param>
        """
        weight = self.CHAT_WEIGHT
        if not features.monologue:
            weight *= self.MONOLOGUE_DISABLED_MULTIPLIER

        self.value = min(self.MAX_ACTIVITY_SCORE, self.value * self.DECAY_FACTOR + weight)
        self.last_activity = datetime.now(timezone.utc)

    def apply_time_decay(self) -> None:
        """
        <summary>
        Decay the score based on elapsed wall-clock time. Call once per decision cycle
        so the score relaxes correctly when chat goes silent.
        </summary>
        """
        now = datetime.now(timezone.utc)
        elapsed = (now - self._last_decay_time).total_seconds()
        self._last_decay_time = now
        if elapsed <= 0:
            return
        periods = elapsed / self.DECAY_INTERVAL_SECONDS
        self.value *= self.DECAY_FACTOR ** periods
