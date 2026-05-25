from src.qubit.cognitive.behaviours.base import Behavior
from src.qubit.core.events import MonologueEvent
from datetime import datetime, timezone
from src.utils.log_utils import get_logger


class FrontendTriggeredMonologueBehavior(Behavior):
    """
    Behavior that triggers an autonomous monologue when a frontend command is received.

    Part of the cognitive layer's pluggable decision strategies (see DecisionEngine).
    Activates only when a frontend_command is present in context (e.g. "start" from UI).

    Role in 2026 SoC refactor:
    - Keeps command-driven monologue logic isolated from the orchestrator and decision engine.
    - Implements the Behavior contract so it can be added/removed/reordered without touching core logic.
    - Complements IdleMonologueBehavior (low-activity) and ChatResponseBehavior (medium-activity).

    Contract:
    - Receives context dict (must contain "frontend_command" key when active).
    - Returns {"type": "monologue", "topic": ...} or None.
    - First behavior returning non-None wins the cycle.
    """

    def __init__(self):
        super().__init__("FrontendMonologue")
        self.cooldown_seconds = 10
        self.logger = get_logger("FrontendTriggeredMonologueBehavior")

    async def tick(self, context: dict):
        """
        Check for pending frontend command and produce a monologue decision if present.

        Args:
            context: Must include optional "frontend_command" (str) from ActivityTracker.

        Returns:
            dict | None: {"type": "monologue", "topic": str} or None if no command.
        """
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
        """Map known frontend commands to monologue topics (fallback to default)."""
        mapping = {
            "start": "welcome to the stream",
            "default": "a random fun fact about Qubit"
        }
        return mapping.get(command.lower(), mapping["default"])
