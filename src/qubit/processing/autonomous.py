"""
<summary>
AutonomousPromptProcessor — emits ResponsePromptEvents for system-triggered monologue prompts.
</summary>
<remarks>
LAYER: Input Processing

The narrow processor responsible for turning monologue_prompt events into generation
intents. It is the only component in Input Processing that emits ResponsePromptEvent
for autonomous (non-user-triggered) speech.

Responsibilities:
  - Drop stale monologue prompts based on max_age_seconds.
  - Construct and publish a ResponsePromptEvent so GenerationCoordinator can assemble
    a full prompt and call the LLM.

All logic deciding when a monologue should happen lives exclusively in the Cognitive
layer (behaviours + DecisionEngine). This processor only executes the emission step
after the decision has been made.
</remarks>
"""

from datetime import datetime, timedelta, timezone

from src.qubit.core.event_processor import EventProcessor
from src.qubit.processing.common import is_stale
from src.qubit.core.events import ResponsePromptEvent


class AutonomousPromptProcessor(EventProcessor):
    """
    <summary>
    Pure EventProcessor for system-generated monologue prompts. Applies a
    staleness check then publishes a ResponsePromptEvent for the Generation layer.
    </summary>
    """

    SUBSCRIPTIONS = {
        "monologue_prompt": "handle_event",
    }

    def __init__(self, max_age_seconds: int = 30):
        """
        <summary>Initialise the processor with a staleness window.</summary>
        <param name="max_age_seconds">Events older than this are dropped as stale.</param>
        """
        super().__init__("autonomous prompt processor")
        self.max_age = timedelta(seconds=max_age_seconds)

    async def handle_event(self, event) -> None:
        """
        <summary>
        Apply the staleness filter, then delegate to _emit_prompt_request.
        </summary>
        <param name="event">The monologue_prompt event from the bus.</param>
        """
        if await is_stale(event, self.max_age, self.logger, context="monologue"):
            return

        await self._emit_prompt_request(event)

    async def _emit_prompt_request(self, event) -> None:
        """
        <summary>
        Build a minimal ResponsePromptEvent from the raw monologue event and publish it.
        Prompt assembly, RAG injection, and LLM calling happen downstream in the
        Generation layer.
        </summary>
        <param name="event">The monologue_prompt event containing the prompt text.</param>
        """
        prompt = getattr(event, "prompt", None) or ""
        prompt_event = ResponsePromptEvent(
            type="response_prompt",
            user="system",
            source=event.type,
            timestamp=datetime.now(timezone.utc).isoformat(),
            data={"user": "system", "prompt": prompt},
            prompt=prompt
        )

        await self.event_bus.publish(prompt_event)
