from src.qubit.cognitive.behaviours.base import Behavior
from src.qubit.core.events import MonologueEvent
from datetime import datetime, timezone
from src.utils.log_utils import get_logger


class FrontendTriggeredMonologueBehavior(Behavior):
    def __init__(self):
        super().__init__("FrontendMonologue")
        self.cooldown_seconds = 10
        self.logger = get_logger("FrontendTriggeredMonologueBehavior")

    async def tick(self, context: dict):
        command = context.get("frontend_command")
        if not command:
            return None

        topic = self._get_topic_for_command(command)
        prompt = f"Talk about {topic}."

        self.logger.info(
            f"[FrontendMonologue] TRIGGERED by frontend command '{command}' → {topic}"
        )

        return {
            "type": "monologue",
            "topic": topic,
        }

    def _get_topic_for_command(self, command: str) -> str:
        mapping = {
            "start": "welcome to the stream",
            "default": "a random fun fact about Qubit"
        }
        return mapping.get(command.lower(), mapping["default"])