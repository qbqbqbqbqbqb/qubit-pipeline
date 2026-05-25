from datetime import datetime, timezone
from src.qubit.core.events import TwitchChatEvent
from src.qubit.cognitive.behaviours.base import Behavior


class ChatResponseBehavior(Behavior):
    """
    Behavior responsible for deciding when and which chat/STT message to respond to.

    Part of the cognitive layer's pluggable decision strategies.

    Behavior:
    - In normal mode (monologue or stt enabled): only activates in the medium
      activity window (3.0–9.0).
    - In pure chat mode (both monologue and stt disabled): responds to any
      pending chat that is still in the queue (no activity gate), so the bot
      answers chats when only chat input is active.

    Role in 2026 SoC refactor:
    - Isolates response-timing and message-selection rules from DecisionEngine and Orchestrator.
    - Implements the Behavior contract, enabling easy addition/removal/reordering of strategies.

    Contract:
    - Receives context dict (activity_score, last_user_input_response_time, queue, etc.).
    - Returns {"type": "response", "best_message": ..., "reason": ...} or None.
    - First non-None decision in the ordered behaviour list wins the cycle.
    """

    def __init__(self):
        super().__init__("ChatResponse")
        self.response_cooldown = 15

    async def tick(self, context: dict) -> dict | None:
        """
        Evaluate activity window + cooldown, then pick best message from priority queue.

        Special case:
        - When both "monologue" and "stt" are disabled (pure chat mode),
          we respond to any pending chat that hasn't decayed from the queue,
          without requiring high activity.
        - When STT or monologues are enabled, we keep the normal activity gate
          so STT has priority when it arrives.
        """
        monologue = context["features"].get("monologue", True)
        stt = context["features"].get("stt", True)
        pure_chat_mode = not monologue and not stt

        if not pure_chat_mode:
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
    
