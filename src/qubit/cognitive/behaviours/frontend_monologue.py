from src.qubit.cognitive.behaviours.base import Behavior
from src.utils.log_utils import get_logger


class FrontendTriggeredMonologueBehavior(Behavior):
    """
    Scored proposal behavior for frontend-driven monologues (start button, random_fact, etc.).

    These are high-intent commands from the operator, so they receive a very high base score.
    Still participates in the global proposal scoring so STT responses can (rarely) win if something
    truly urgent is in the queue.
    """

    def __init__(self):
        super().__init__("FrontendMonologue")
        self.logger = get_logger("FrontendTriggeredMonologueBehavior")

    async def tick(self, context: dict):
        command = context.get("frontend_command")
        if not command:
            return None

        topic = self._get_topic_for_command(command)

        # Frontend commands are operator intent → very high priority
        # but still below live STT (the +10 tie-breaker in DecisionEngine protects streamer voice)
        score = 1.35

        self.logger.info(
            f"[FrontendMonologue] PROPOSAL | score={score:.2f} | command='{command}' → {topic}"
        )

        return {
            "type": "monologue",
            "score": score,
            "reason": f"frontend_{command}",
            "topic": topic,
        }

    def _get_topic_for_command(self, command: str) -> str:
        mapping = {
            "start": "welcome to the stream",
            "random_fact": "a random fun fact about Qubit",
            "default": "a random fun fact about Qubit",
        }
        return mapping.get(command.lower(), mapping["default"])
