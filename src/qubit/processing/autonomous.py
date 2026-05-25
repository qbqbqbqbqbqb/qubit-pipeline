"""
Autonomous / monologue prompt processor (EventProcessor).

LAYER: Input Processing (see ARCHITECTURE.md)

This is the focused processor for system-generated monologue prompts and the
initial "start_message" event.

Responsibilities:
- Staleness filtering (drop old monologue prompts)
- Memory forwarding (so monologues appear in long-term memory)
- Emitting ResponsePromptEvent for the Generation layer

This processor is intentionally small. All decision logic about *when* to
emit a monologue lives in the Cognitive layer (FrontendTriggeredMonologueBehavior etc.).
Prompt formatting for monologues lives here (previously in transitional PromptRequestBuilder).
"""

from datetime import datetime, timedelta, timezone

from src.qubit.core.event_processor import EventProcessor
from src.qubit.processing.common import is_stale, forward_to_memory
from src.qubit.core.events import ResponsePromptEvent


class AutonomousPromptProcessor(EventProcessor):
    """
    Pure EventProcessor for monologue and start-message events.

    It performs mechanical filtering + memory + prompt-request emission.
    It does not decide *when* monologues should happen.
    """

    SUBSCRIPTIONS = {
        "monologue_prompt": "handle_event",
        "start_message": "handle_event",
    }

    def __init__(self, max_age_seconds: int = 30, memory_writer=None, event_bus=None):
        super().__init__("autonomous prompt processor")
        self.max_age = timedelta(seconds=max_age_seconds)
        self.memory_writer = memory_writer
        self.event_bus = event_bus

    async def handle_event(self, event) -> None:
        if await is_stale(event, self.max_age, self.logger, context="monologue"):
            return

        await forward_to_memory(event, self.memory_writer, self.logger)
        await self._emit_prompt_request(event)

    async def _emit_prompt_request(self, event) -> None:
        """
        Turn the monologue/start event into a ResponsePromptEvent and publish it.
        Prompt formatting previously lived in transitional PromptRequestBuilder.
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

        if self.event_bus:
            await self.event_bus.publish(prompt_event)
        else:
            self.logger.warning("[AutonomousPromptProcessor] No event_bus - cannot emit monologue prompt")
