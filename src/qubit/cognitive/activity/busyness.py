"""
ActivityScore - the chat-only "how busy is chat" scalar.

"""

from datetime import datetime, timezone


class ActivityScore:
    MAX_ACTIVITY_SCORE = 15.0
    CHAT_WEIGHT = 1.0
    MONOLOGUE_DISABLED_MULTIPLIER = 0.3
    DECAY_FACTOR = 0.85

    DECAY_INTERVAL_SECONDS = 5.0

    def __init__(self):
        self.value = 0.0
        self.last_activity = datetime.now(timezone.utc)
        self._last_decay_time = datetime.now(timezone.utc)

    def register_chat_message(self, features: dict) -> None:
        """Bump the score for one incoming chat message, with the usual per-event decay."""
        weight = self.CHAT_WEIGHT
        if not features.get("monologue", True):
            weight *= self.MONOLOGUE_DISABLED_MULTIPLIER

        self.value = min(self.MAX_ACTIVITY_SCORE, self.value * self.DECAY_FACTOR + weight)
        self.last_activity = datetime.now(timezone.utc)

    def apply_time_decay(self) -> None:
        """
        Decay based on elapsed wall-clock time, independent of whether any
        new chat message arrived. 
        """
        now = datetime.now(timezone.utc)
        elapsed = (now - self._last_decay_time).total_seconds()
        self._last_decay_time = now
        if elapsed <= 0:
            return
        periods = elapsed / self.DECAY_INTERVAL_SECONDS
        self.value *= self.DECAY_FACTOR ** periods