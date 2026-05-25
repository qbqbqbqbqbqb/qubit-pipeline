"""
ActivityTracker - pure state holder for cognitive decision context.

LAYER: Cognitive

This class maintains all the dynamic state that feeds into the DecisionEngine
and its behaviours. It is the single place where:

- Activity score is computed and decayed
- Input events are queued with priorities
- Frontend commands are staged for the next decision cycle

It is deliberately not a Service or EventProcessor; it is a pure data structure
with mutation methods, used only by the CognitiveOrchestrator and DecisionEngine.

No other layer should read or write this state directly.
"""

from datetime import datetime, timezone
from src.qubit.cognitive.priority_queue import InputPriorityQueue


class ActivityTracker:
    """
    LAYER: Cognitive (pure state holder for all decision-making context)

    This is the single source of truth for everything the DecisionEngine
    and behaviours need to make a choice:

    - Current activity_score (decays, boosted by input)
    - Pending messages (via InputPriorityQueue)
    - Last activity timestamps
    - Most recent frontend command (e.g. "start", "random_fact")

    CognitiveOrchestrator only feeds data into this tracker.
    DecisionEngine only reads from it (via the context dict).
    No other layer should touch this object.
    """

    def __init__(self):
        self.activity_score = 0.0
        self.last_activity = datetime.now(timezone.utc)
        self.queue = InputPriorityQueue(maxlen=12)

        # The only piece of external "intent" state we currently care about
        self._current_frontend_command: str | None = None

    async def handle_input(self, event, features: dict):
        """
        Process a new input event: update activity score and enqueue it.

        Short or empty text is ignored. The source is derived from event type
        to apply appropriate weighting (STT gets higher weight).
        """
        source = self._get_source(event)
        text = event.data.get("text", "") if hasattr(event, "data") else getattr(event, "text", "")
        if len(text.strip()) < 3:
            return

        self._update_activity_score(source, features)
        self.queue.add(text, source, event)

    def set_frontend_command(self, command: str | None):
        """
        Stage a frontend command (e.g. "monologue" or "random_fact") for the
        next decision cycle. Called by the orchestrator on frontend_command events.
        """
        self._current_frontend_command = command

    def consume_frontend_command(self) -> str | None:
        """
        Return the staged frontend command (if any) and clear it.

        This ensures each command is consumed exactly once by the decision context.
        """
        cmd = self._current_frontend_command
        self._current_frontend_command = None
        return cmd

    def _get_source(self, event) -> str:
        """Map event type to a canonical source string used for weighting and queuing."""
        type_map = {
            "stt_processed": "user_input_stt",
            "twitch_chat_processed": "user_input_chat_message",
            "kick_chat_processed": "user_input_chat_message",
            "user_event_follow": "user_event_follow",
            "user_event_subscription": "user_event_subscription",
            "user_event_raid": "user_event_raid",
        }
        return type_map.get(event.type, "other")

    def _update_activity_score(self, source: str, features: dict):
        """
        Decay the activity score and add a weighted boost based on input source
        and current feature flags (e.g. STT disabled or monologue disabled).
        """
        weight = 5.0 if source == "user_input_stt" else 1.0
        if not features.get("stt", True) and source == "user_input_stt":
            weight = 0.0
        if not features.get("monologue", True):
            weight *= 0.3

        self.activity_score = min(15.0, self.activity_score * 0.85 + weight)
        self.last_activity = datetime.now(timezone.utc)
