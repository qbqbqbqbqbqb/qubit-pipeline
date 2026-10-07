"""
ActivityTracker - pure state holder for cognitive decision context.

LAYER: Cognitive

Maintains all dynamic state that feeds into DecisionEngine and its behaviours:
"""

from datetime import datetime, timezone

from src.qubit.cognitive.priority_queue import InputPriorityQueue


class ActivityTracker:
    # Event type -> canonical source string, used for weighting and queuing.
    SOURCE_BY_EVENT_TYPE = {
        "stt_processed": "user_input_stt",
        "twitch_chat_processed": "user_input_chat_message",
        "kick_chat_processed": "user_input_chat_message",
        "user_event_follow": "user_event_follow",
        "user_event_subscription": "user_event_subscription",
        "user_event_raid": "user_event_raid",
    }
    DEFAULT_SOURCE = "other"


    FEATURE_FLAG_BY_SOURCE = {
        "user_input_stt": "stt",
        "user_input_chat_message": "chat",
        "user_event_raid": "raids",
        "user_event_follow": "raids",
    }
   
    GIFT_SUB_TYPES = {"gift"}


    EVENT_SOURCES = {"user_event_raid", "user_event_subscription", "user_event_follow"}

    MIN_TEXT_LENGTH = 3

    ACTIVITY_DECAY_FACTOR = 0.85
    MAX_ACTIVITY_SCORE = 15.0
    CHAT_WEIGHT = 1.0
    MONOLOGUE_DISABLED_MULTIPLIER = 0.3


    ACTIVITY_DECAY_INTERVAL_SECONDS = 5.0

    QUEUE_MAXLEN = 12

    def __init__(self):
        self.activity_score = 0.0
        self.last_activity = datetime.now(timezone.utc)
        self._last_decay_time = datetime.now(timezone.utc)
        self.queue = InputPriorityQueue(maxlen=self.QUEUE_MAXLEN)
        self.pending_events: list[dict] = []


        self._current_frontend_command: str | None = None

    async def handle_input(self, event, features: dict) -> None:
        """Process a new input event: gate on feature flags, then route it."""
        source = self._get_source(event)

        flag = self._feature_flag_for(source, event)
        if flag and not features.get(flag, True):
            return 

        if source in self.EVENT_SOURCES:

            self.pending_events.append(self._extract_event_detail(event, source))
            return

        text = self._extract_text(event)
        if len(text.strip()) < self.MIN_TEXT_LENGTH:
            return

        if source == "user_input_chat_message":

            self._update_activity_score(features)

        self.queue.add(text, source, event)

    def apply_time_decay(self) -> None:
        """
        Decay activity_score based on elapsed wall-clock time, independent of
        whether any new chat message arrived. Without this, activity_score
        only changes inside handle_input() — so if chat goes truly silent
        after a busy period, the score stays frozen instead of relaxing
        down. Call this once per decision cycle.
        """
        now = datetime.now(timezone.utc)
        elapsed = (now - self._last_decay_time).total_seconds()
        self._last_decay_time = now
        if elapsed <= 0:
            return
        periods = elapsed / self.ACTIVITY_DECAY_INTERVAL_SECONDS
        self.activity_score *= self.ACTIVITY_DECAY_FACTOR ** periods

    def set_frontend_command(self, command: str | None) -> None:
        """Stage a frontend command (e.g. 'monologue' or 'random_fact') for the next cycle."""
        self._current_frontend_command = command

    def peek_frontend_command(self) -> str | None:
        """Non-destructive read for building context — a losing proposal must not lose the command."""
        return self._current_frontend_command

    def consume_frontend_command(self) -> str | None:
        """Return and clear the staged frontend command. Call only once it has actually executed."""
        cmd = self._current_frontend_command
        self._current_frontend_command = None
        return cmd

    def peek_pending_events(self) -> list[dict]:
        """Non-destructive read for building context."""
        return list(self.pending_events)

    def remove_pending_events(self, events: list[dict]) -> None:
        """Remove exactly the given events (by equality), e.g. after they've been acknowledged."""
        for e in events:
            if e in self.pending_events:
                self.pending_events.remove(e)


    def _update_activity_score(self, features: dict) -> None:
        """Decay the activity score and add a weighted boost. Chat messages only."""
        weight = self.CHAT_WEIGHT
        if not features.get("monologue", True):
            weight *= self.MONOLOGUE_DISABLED_MULTIPLIER

        self.activity_score = min(
            self.MAX_ACTIVITY_SCORE,
            self.activity_score * self.ACTIVITY_DECAY_FACTOR + weight,
        )
        self.last_activity = datetime.now(timezone.utc)