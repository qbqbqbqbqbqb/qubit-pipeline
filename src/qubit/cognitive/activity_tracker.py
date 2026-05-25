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
        source = self._get_source(event)
        text = event.data.get("text", "") if hasattr(event, "data") else getattr(event, "text", "")
        if len(text.strip()) < 3:
            return

        self._update_activity_score(source, features)
        self.queue.add(text, source, event)

    def set_frontend_command(self, command: str | None):
        """Called by CognitiveOrchestrator when a frontend_command event arrives."""
        self._current_frontend_command = command

    def consume_frontend_command(self) -> str | None:
        """
        Returns the current frontend command (if any) and clears it.
        This is the clean hand-off to the decision context.
        """
        cmd = self._current_frontend_command
        self._current_frontend_command = None
        return cmd

    def _get_source(self, event) -> str:
        type_map = {
            "stt_processed": "user_input_stt",
            "twitch_chat_processed": "user_input_chat_message",
            "user_event_follow": "user_event_follow",
            "user_event_subscription": "user_event_subscription",
            "user_event_raid": "user_event_raid",
        }
        return type_map.get(event.type, "other")

    def _update_activity_score(self, source: str, features: dict):
        weight = 5.0 if source == "user_input_stt" else 1.0
        if not features.get("stt", True) and source == "user_input_stt":
            weight = 0.0
        if not features.get("monologue", True):
            weight *= 0.3

        self.activity_score = min(15.0, self.activity_score * 0.85 + weight)
        self.last_activity = datetime.now(timezone.utc)
