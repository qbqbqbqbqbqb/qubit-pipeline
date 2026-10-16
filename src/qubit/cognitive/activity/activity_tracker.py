"""
<summary>
ActivityTracker — pure state holder for the cognitive decision context.
</summary>
<remarks>
LAYER: Cognitive

Coordinates three collaborators:
  - ActivityScore:       chat-only busyness scalar (busyness.py)
  - InputPriorityQueue:  chat/STT messages (../priority_queue.py)
  - CommunityEventQueue: pending raid/gift/follow reactions (community_event_queue.py)

Event interpretation (source identification, feature flag lookup, field extraction)
is delegated to EventAdapter (event_adapter.py) — this class does not inspect
the shape of raw Event objects directly.

Not a Service or EventProcessor. Used only by CognitiveOrchestrator and
DecisionEngine. No other layer should read or write this state.
</remarks>
"""

from datetime import datetime

from src.qubit.cognitive.activity.busyness import ActivityScore
from src.qubit.cognitive.activity.community_event_queue import CommunityEventQueue
from src.qubit.cognitive.activity.event_adapter import EventAdapter
from src.qubit.cognitive.priority_queue import InputPriorityQueue


class ActivityTracker:
    """
    <summary>
    Thin coordinator over ActivityScore, InputPriorityQueue, and CommunityEventQueue.
    Provides the shared state that DecisionEngine reads each cycle.
    </summary>
    """

    MIN_TEXT_LENGTH = 3
    QUEUE_MAXLEN = 12

    def __init__(self, mention_whitelist: frozenset[str] | None = None):
        """
        <summary>Initialise all collaborator state objects.</summary>
        <param name="mention_whitelist">
        Lowercased names that earn a mention bonus in the priority queue scorer.
        </param>
        """
        self.busyness = ActivityScore()
        self.queue = InputPriorityQueue(maxlen=self.QUEUE_MAXLEN, mention_whitelist=mention_whitelist)
        self.events = CommunityEventQueue()
        self._current_frontend_command: str | None = None

    @property
    def activity_score(self) -> float:
        """<summary>Current chat busyness scalar. Read by DecisionEngine each cycle.</summary>"""
        return self.busyness.value

    @property
    def last_activity(self) -> datetime:
        """<summary>Timestamp of the most recent chat message that updated the busyness score.</summary>"""
        return self.busyness.last_activity

    async def handle_input(self, event, features) -> None:
        """
        <summary>
        Process a new input event: gate on feature flags, then route to the
        appropriate queue or drop entirely.
        </summary>
        <param name="event">The processed input event from the bus.</param>
        <param name="features">The current FeatureFlags instance.</param>
        """
        source = EventAdapter.get_source(event)

        flag = EventAdapter.feature_flag_for(source, event)
        if flag and not getattr(features, flag, True):
            return

        if source in EventAdapter.EVENT_SOURCES:
            # Community events (raids/gifts/follows) bypass the busyness score —
            # they win through priority tiers in DecisionEngine, not chat volume.
            self.events.add(EventAdapter.extract_event_detail(event, source))
            return

        text = EventAdapter.extract_text(event)
        if len(text.strip()) < self.MIN_TEXT_LENGTH:
            return

        if source == "user_input_chat_message":
            self.busyness.register_chat_message(features)

        self.queue.add(text, source, event)

    def apply_time_decay(self) -> None:
        """<summary>Apply wall-clock-based decay to the busyness score. Called once per decision tick.</summary>"""
        self.busyness.apply_time_decay()

    def set_frontend_command(self, command: str | None) -> None:
        """
        <summary>Stage a frontend command for the next decision cycle.</summary>
        <param name="command">The command string (e.g. 'monologue', 'random_fact'), or None to clear.</param>
        """
        self._current_frontend_command = command

    def peek_frontend_command(self) -> str | None:
        """
        <summary>Non-destructive read of the staged frontend command.</summary>
        <returns>The command string, or None if none is staged.</returns>
        """
        return self._current_frontend_command

    def consume_frontend_command(self) -> str | None:
        """
        <summary>Return and clear the staged frontend command. Call only after it has executed.</summary>
        <returns>The command string that was consumed, or None.</returns>
        """
        cmd = self._current_frontend_command
        self._current_frontend_command = None
        return cmd

    def peek_pending_events(self) -> list[dict]:
        """<summary>Non-destructive read of all pending community events.</summary>"""
        return self.events.peek()

    def remove_pending_events(self, events: list[dict]) -> None:
        """
        <summary>Remove exactly the given community events by their assigned ids.</summary>
        <param name="events">List of event dicts to remove (each must contain '_id').</param>
        """
        self.events.remove(events)
