from datetime import datetime, timezone
from src.qubit.core.events import TwitchChatEvent
from src.qubit.cognitive.behaviours.base import Behavior, BehaviorContext

class ChatResponseBehavior(Behavior):
    """
    Behavior responsible for deciding when and which chat/STT message to respond to.

    It only activates in the "medium activity" window and always picks the
    highest-priority message using the shared InputPriorityQueue.
    """

    def __init__(self):
        super().__init__("ChatResponse")
        self.response_cooldown = 25

    async def tick(self, context: dict) -> dict | None:
        """
        Decide whether to respond and which message to pick.

        Returns:
            dict | None: Decision dict with best_message or None if no response should happen
        """
        if not (3.0 <= context["activity_score"] <= 9.0):
            return None

        now = datetime.now(timezone.utc)
        if (now - context["last_user_input_response_time"]).total_seconds() < self.response_cooldown:
            return None

        best = context["queue"].get_best()
        if not best:
            return None

        return TwitchChatEvent(
            type="twitch_chat_chosen",
            user=best.user if hasattr(best, "user") else "unknown",
            timestamp=now.isoformat(),
            data={
                "message": best,
                "reason": "chat_response"
            },
            prompt=best.content if hasattr(best, "content") else str(best),
        )
    