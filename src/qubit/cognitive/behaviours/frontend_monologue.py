"""
FrontendTriggeredMonologueBehavior - scored proposal for frontend-driven
monologues (start button, random_fact, etc.).

These are high-intent commands from the operator, so they receive a high
base score — but still participate in normal proposal scoring so a live STT
message can occasionally outrank them (protected by DecisionEngine's STT
tie-breaker).
"""

from src.qubit.cognitive.behaviours.base import Behavior
from src.utils.log_utils import get_logger


class FrontendTriggeredMonologueBehavior(Behavior):
    # Operator commands always mean maximum willingness from this behavior's
    # own perspective — there's no "how eager" curve here, just on/off. The
    # actual priority this carries relative to ChatResponse/IdleMonologue is
    # set in DecisionEngine.BEHAVIOR_WEIGHTS, not here. RAW_PRIORITY is kept
    # only as the value that table should use to reproduce today's behavior.
    RAW_PRIORITY = 1.35
    NORMALIZED_SCORE = 1.0

    TOPIC_MAP = {
        "start": "welcome to the stream",
        "random_fact": "a random fun fact about Qubit",
    }
    DEFAULT_TOPIC = "a random fun fact about Qubit"

    def __init__(self):
        super().__init__("FrontendMonologue")
        self.logger = get_logger("FrontendTriggeredMonologueBehavior")

    async def tick(self, context: dict) -> dict | None:
        command = context.get("frontend_command")
        if not command:
            return None

        topic = self._get_topic_for_command(command)

        self.logger.info(
            "[FrontendMonologue] PROPOSAL | score=%.2f | command='%s' -> %s",
            self.NORMALIZED_SCORE, command, topic,
        )

        return {
            "type": "monologue",
            "score": self.NORMALIZED_SCORE,
            "reason": f"frontend_{command}",
            "topic": topic,
        }

    def _get_topic_for_command(self, command: str) -> str:
        return self.TOPIC_MAP.get(command.lower(), self.DEFAULT_TOPIC)