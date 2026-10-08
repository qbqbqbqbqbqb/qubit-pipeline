"""
FrontendTriggeredMonologueBehavior - scored proposal for frontend-driven
monologues (start button, random_fact, etc.).

These are high-intent commands from the operator, so they receive a high
base score — but still participate in normal proposal scoring so a live STT
message can occasionally outrank them (protected by DecisionEngine's STT
tie-breaker).
"""

from src.qubit.cognitive.behaviours.base import Behavior
from src.qubit.utils.log_utils import get_logger


class FrontendTriggeredMonologueBehavior(Behavior):
    # Operator commands always mean maximum willingness from this behavior's
    # own perspective — there's no "how eager" curve here, just on/off. The
    # actual priority this carries relative to ChatResponse/IdleMonologue is
    # set in DecisionEngine.BEHAVIOR_WEIGHTS, not here. RAW_PRIORITY is kept
    # only as the value that table should use to reproduce today's behavior.
    RAW_PRIORITY = 1.35
    NORMALIZED_SCORE = 1.0

    PROMPT_MAP = {
        "start": (
            "Welcome viewers to the stream. Be warm, energetic, and a little self-aware "
            "about being an AI VTuber. Keep it short — this is an opener, not a speech."
        ),
        "random_fact": (
            "Share a random fun fact about yourself as an AI, about streaming, or about "
            "something genuinely interesting. Keep it snappy."
        ),
    }
    DEFAULT_PROMPT = (
        "Say something interesting or fun — your choice. Keep it natural and in character."
    )

    def __init__(self):
        super().__init__("FrontendMonologue")
        self.logger = get_logger("FrontendTriggeredMonologueBehavior")

    async def tick(self, context: dict) -> dict | None:
        command = context.get("frontend_command")
        if not command:
            return None

        prompt = self.PROMPT_MAP.get(command.lower(), self.DEFAULT_PROMPT)

        self.logger.info(
            "[FrontendMonologue] PROPOSAL | score=%.2f | command='%s'",
            self.NORMALIZED_SCORE, command,
        )

        return {
            "type": "monologue",
            "score": self.NORMALIZED_SCORE,
            "reason": f"frontend_{command}",
            "prompt": prompt,
            "label": f"frontend_{command}",
        }