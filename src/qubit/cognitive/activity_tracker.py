from datetime import datetime, timezone
from src.qubit.cognitive.priority_queue import InputPriorityQueue

class ActivityTracker:
    """
    Only responsible for activity score + routing input to the priority queue.
    No more pending_messages logic here.
    """

    def __init__(self):
        self.activity_score = 0.0
        self.last_activity = datetime.now(timezone.utc)
        self.queue = InputPriorityQueue(maxlen=12)

    async def handle_input(self, event, features: dict):
        source = self._get_source(event)
        text = event.data.get("text", "") if hasattr(event, "data") else getattr(event, "text", "")
        if len(text.strip()) < 3:
            return

        self._update_activity_score(source, features)
        self.queue.add(text, source, event)

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