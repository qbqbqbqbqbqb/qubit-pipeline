"""
ActivityScore - the chat-only "how busy is chat" scalar.

Driven ONLY by written chat messages (register_chat_message is called for
user_input_chat_message only). STT and community events (raids/gifts/
follows) deliberately do not touch this — they win through DecisionEngine's
priority tiers, independent of how busy chat looks. Feeding STT into this
score used to make heavy STT talking suppress chat responsiveness even when
chat itself was quiet; that coupling has been removed.
"""

from datetime import datetime, timezone


class ActivityScore:
    MAX_ACTIVITY_SCORE = 15.0
    CHAT_WEIGHT = 1.0
    MONOLOGUE_DISABLED_MULTIPLIER = 0.3
    DECAY_FACTOR = 0.85

    # How often apply_time_decay() expects to be called — matches the
    # cognitive decision cycle cadence. Decay is computed from actual
    # elapsed wall-clock time, so this only affects how DECAY_FACTOR is
    # scaled, not correctness if the caller's cadence drifts.
    DECAY_INTERVAL_SECONDS = 5.0

    def __init__(self):
        self.value = 0.0
        self.last_activity = datetime.now(timezone.utc)
        self._last_decay_time = datetime.now(timezone.utc)

    def register_chat_message(self, features) -> None:
        """Bump the score for one incoming chat message, with the usual per-event decay."""
        weight = self.CHAT_WEIGHT
        if not features.monologue:
            weight *= self.MONOLOGUE_DISABLED_MULTIPLIER

        self.value = min(self.MAX_ACTIVITY_SCORE, self.value * self.DECAY_FACTOR + weight)
        self.last_activity = datetime.now(timezone.utc)

    def apply_time_decay(self) -> None:
        """
        Decay based on elapsed wall-clock time, independent of whether any
        new chat message arrived. Without this, the score only changes on
        register_chat_message() — so if chat goes truly silent after a busy
        period, the score stays frozen instead of relaxing down. Call this
        once per decision cycle.
        """
        now = datetime.now(timezone.utc)
        elapsed = (now - self._last_decay_time).total_seconds()
        self._last_decay_time = now
        if elapsed <= 0:
            return
        periods = elapsed / self.DECAY_INTERVAL_SECONDS
        self.value *= self.DECAY_FACTOR ** periods