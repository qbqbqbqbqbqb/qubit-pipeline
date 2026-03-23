from src.qubit.cognitive.behaviours.base import Behavior
import random
from datetime import datetime, timezone

from src.qubit.utils.log_utils import get_logger

class FrontendTriggeredMonologueBehavior(Behavior):
    def __init__(self):
        super().__init__("FrontendMonologue")
        self.cooldown_seconds = 10
        self.logger = get_logger("FrontendTriggeredMonologueBehavior")

    async def tick(self, context: dict) -> dict | None:
        command = context.get("frontend_command")
        if not command:
            return None

        topic = self._get_topic_for_command(command)
        self.logger.info(f"[FrontendMonologue] TRIGGERED by frontend command '{command}' → {topic}")

        return {
            "type": "monologue",
            "topic": topic,
            "reason": f"frontend_{command}"
        }

    def _get_topic_for_command(self, command: str) -> str:
        mapping = {
            "start": "welcome to the stream",
            "default": "a random fun fact about Qubit"
        }
        return mapping.get(command.lower(), mapping["default"])