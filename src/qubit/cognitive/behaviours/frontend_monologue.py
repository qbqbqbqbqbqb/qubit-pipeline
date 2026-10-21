"""
<summary>
FrontendTriggeredMonologueBehavior — scored proposal for frontend-driven monologues
such as the start button and random_fact commands.
</summary>
<remarks>
These are high-intent operator commands and receive a high base score, but still
participate in normal proposal scoring so a live STT message can occasionally outrank them.
</remarks>
"""

from src.qubit.cognitive.behaviours.base import Behavior
from src.qubit.utils.log_utils import get_logger


class FrontendTriggeredMonologueBehavior(Behavior):
    """
    <summary>
    Proposes a monologue when the frontend has staged a command (e.g. 'start', 'random_fact').
    Maps command strings to authored prompt instructions.
    </summary>
    """

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
        "end_stream": (
            "Say goodbye to the stream. Thank the viewers for watching, be warm and genuine. "
            "Keep it short — this is a sign-off, not a recap."
        ),
    }
    DEFAULT_PROMPT = (
        "Say something interesting or fun — your choice. Keep it natural and in character."
    )

    def __init__(self):
        super().__init__("FrontendMonologue")
        self.logger = get_logger("FrontendTriggeredMonologueBehavior")

    async def tick(self, context: dict) -> dict | None:
        """
        <summary>
        Return a monologue proposal if a frontend command is staged, or None if none is present.
        </summary>
        <param name="context">The cycle context dict from DecisionEngine.</param>
        <returns>A monologue proposal dict, or None.</returns>
        """
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