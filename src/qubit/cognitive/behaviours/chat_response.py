from datetime import datetime, timezone
from src.qubit.core.events import TwitchChatEvent
from src.qubit.cognitive.behaviours.base import Behavior


class ChatResponseBehavior(Behavior):
    """
    Behavior responsible for deciding when and which chat/STT message to respond to.

    Part of the cognitive layer's pluggable decision strategies.
    Only activates in the "medium activity" window (3.0–9.0) and always selects the
    highest-priority pending message via the shared InputPriorityQueue.

    Role in 2026 SoC refactor:
    - Isolates response-timing and message-selection rules from DecisionEngine and Orchestrator.
    - Implements the Behavior contract, enabling easy addition/removal/reordering of strategies.
    - Complements IdleMonologueBehavior (low activity) and FrontendTriggeredMonologueBehavior.

    Contract:
    - Receives context dict (activity_score, last_user_input_response_time, queue, etc.).
    - Returns {"type": "response", "best_message": ..., "reason": ...} or None.
    - First non-None decision in the ordered behaviour list wins the cycle.
    """

    def __init__(self):
        super().__init__("ChatResponse")
        self.response_cooldown = 25

    async def tick(self, context: dict) -> dict | None:
        """
        Evaluate activity window + cooldown, then pick best message from priority queue.

        Args:
            context: Snapshot from ActivityTracker + feature flags + InputPriorityQueue.

        Returns:
            dict | None: Decision with best_message or None if conditions not met.
        """
        if not (3.0 <= context["activity_score"] <= 9.0):
            return None

        now = datetime.now(timezone.utc)
        if (now - context["last_user_input_response_time"]).total_seconds() < self.response_cooldown:
            return None

        best = context["queue"].get_best()
        if not best:
            return None

        return {
            "type": "response",
            "best_message": best,
            "reason": "chat_response"
        }
    
