"""
Autonomous / monologue prompt processor (EventProcessor).

LAYER: Input Processing (see ARCHITECTURE.md)

This is the focused processor for system-generated monologue prompts and the
initial "start_message" event.

Responsibilities:
- Staleness filtering (drop old monologue prompts)
- Memory forwarding (so monologues appear in long-term memory)
- Converting the event into a proper prompt request and handing it to the
  prompt builder / dispatcher for the Generation layer

This processor is intentionally small. All decision logic about *when* to
emit a monologue lives in the Cognitive layer (FrontendTriggeredMonologueBehavior etc.).

The prompt-building step still goes through the transitional PromptRequestBuilder
(see prompt_builder.py). That will be folded into GenerationCoordinator in a later phase.
"""

from datetime import timedelta

from src.qubit.core.event_processor import EventProcessor
from src.qubit.processing.common import is_stale, forward_to_memory


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

    def __init__(self, max_age_seconds: int = 30, prompt_handler=None, memory_writer=None):
        super().__init__("autonomous prompt processor")
        self.max_age = timedelta(seconds=max_age_seconds)
        self.prompt_handler = prompt_handler
        self.memory_writer = memory_writer

    async def handle_event(self, event) -> None:
        if await is_stale(event, self.max_age, self.logger, context="monologue"):
            return

        await forward_to_memory(event, self.memory_writer, self.logger)
        await self._emit_prompt_request(event)

    async def _emit_prompt_request(self, event) -> None:
        """
        Turn the monologue/start event into a ResponsePromptEvent and enqueue it.
        This is the only place this processor touches the prompt-building path.
        """
        if self.prompt_handler and event.type in self.prompt_handler.builders:
            builder = self.prompt_handler.builders[event.type]
            prompt_event = builder(event)
            await self.prompt_handler.dispatcher.enqueue(prompt_event)
        else:
            self.logger.warning("[AutonomousPromptProcessor] No prompt builder found for event type: %s", event.type)
