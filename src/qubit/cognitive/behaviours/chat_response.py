from datetime import datetime, timezone
from src.qubit.core.events import TwitchChatEvent
from src.qubit.cognitive.behaviours.base import Behavior


class ChatResponseBehavior(Behavior):
    """
    Behavior responsible for deciding when and which chat/STT message to respond to.

    Behavior:
    - When monologue or live STT input is present: only activates inside the
      medium activity window (3.0–9.0) so high-priority voice can win.
    - Pure-chat mode (monologue off AND no live STT speech in queue): answers
      any pending chat without requiring activity score. The "stt" flag alone
      no longer forces the gate — only actual spoken input does.

    Contract:
    - Receives context dict (activity_score, last_user_input_response_time, queue, etc.).
    - Returns {"type": "response", ...} or None.
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
        stt_flag = context["features"].get("stt", True)
        # Pure-chat behaviour applies unless STT is *actually* delivering input right now.
        # This way the "stt" flag alone does not force the activity gate for chat.
        has_live_stt = context["queue"].has_source("user_input_stt") if stt_flag else False
        pure_chat_mode = not monologue and not has_live_stt

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
    
