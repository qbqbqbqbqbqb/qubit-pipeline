"""
ActivityTracker - pure state holder for cognitive decision context.

LAYER: Cognitive

Thin coordinator over three collaborators:
- ActivityScore: chat-only "how busy is chat" scalar (busyness.py)
- InputPriorityQueue: chat/STT messages (../priority_queue.py)
- CommunityEventQueue: pending raid/gift/follow reactions (community_event_queue.py)
Event interpretation (which source, which feature flag, field extraction)
is delegated to EventAdapter (event_adapter.py) — this class doesn't know
anything about the shape of raw Event objects itself.

Deliberately not a Service or EventProcessor — used only by
CognitiveOrchestrator and DecisionEngine. No other layer should read or
write this state directly.
"""

from datetime import datetime

from src.qubit.cognitive.activity.busyness import ActivityScore
from src.qubit.cognitive.activity.community_event_queue import CommunityEventQueue
from src.qubit.cognitive.activity.event_adapter import EventAdapter
from src.qubit.cognitive.priority_queue import InputPriorityQueue


class ActivityTracker:
    MIN_TEXT_LENGTH = 3
    QUEUE_MAXLEN = 12

    def __init__(self, mention_whitelist: frozenset[str] | None = None):
        self.busyness = ActivityScore()
        self.queue = InputPriorityQueue(maxlen=self.QUEUE_MAXLEN, mention_whitelist=mention_whitelist)
        self.events = CommunityEventQueue()

        # The only piece of external "intent" state tracked directly here —
        # small enough not to warrant its own file.
        self._current_frontend_command: str | None = None

    @property
    def activity_score(self) -> float:
        """DecisionEngine reads this name — kept stable across the split."""
        return self.busyness.value

    @property
    def last_activity(self) -> datetime:
        return self.busyness.last_activity

    async def handle_input(self, event, features) -> None:
        """Process a new input event: gate on feature flags, then route it."""
        source = EventAdapter.get_source(event)

        flag = EventAdapter.feature_flag_for(source, event)
        if flag and not getattr(features, flag, True):
            return  # this input channel is switched off — drop entirely, not just unscored

        if source in EventAdapter.EVENT_SOURCES:
            # Raids/gifts/follows never touch activity_score — they're a
            # separate, always-wins category, not a measure of chat busyness.
            self.events.add(EventAdapter.extract_event_detail(event, source))
            return

        text = EventAdapter.extract_text(event)
        if len(text.strip()) < self.MIN_TEXT_LENGTH:
            return

        if source == "user_input_chat_message":
            # The ONLY source that feeds activity_score/"busyness".
            self.busyness.register_chat_message(features)

        self.queue.add(text, source, event)

    def apply_time_decay(self) -> None:
        self.busyness.apply_time_decay()

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
        return self.events.peek()

    def remove_pending_events(self, events: list[dict]) -> None:
        self.events.remove(events)