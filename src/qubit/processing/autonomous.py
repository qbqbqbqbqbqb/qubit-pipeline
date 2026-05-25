"""
Autonomous / monologue prompt processor (pure EventProcessor).

LAYER: Input Processing

This file implements the narrow processor responsible for turning
system-triggered monologue events into high-level generation intents.

It is the only place in the Input Processing layer that emits
ResponsePromptEvent objects for autonomous (non-user-triggered) speech.

Key responsibilities:
- Drop stale monologue prompts based on configurable max age.
- Forward raw events to MemoryWriter so monologues are recorded for RAG/reflections.
- Construct and publish a ResponsePromptEvent (type="response_prompt") so the
  GenerationCoordinator can assemble a full prompt and call the LLM.

All logic that decides *when* a monologue should happen lives exclusively in
the Cognitive layer (behaviours + DecisionEngine). This processor only
executes the emission step after the decision has been made.

It replaced the older transitional PromptRequestBuilder logic during the 2026 SoC refactor.
"""

from datetime import datetime, timedelta, timezone

from src.qubit.core.event_processor import EventProcessor
from src.qubit.processing.common import is_stale, forward_to_memory
from src.qubit.core.events import ResponsePromptEvent


class AutonomousPromptProcessor(EventProcessor):
    """
    Pure EventProcessor for system-generated monologue and startup prompts.

    It performs three mechanical steps for events that the Cognitive layer has
    already decided should trigger autonomous speech:
    1. Staleness check (drop old monologue_prompt / start_message events).
    2. Forward the raw event to MemoryWriter (monologues must be remembered).
    3. Emit a ResponsePromptEvent so GenerationCoordinator can produce speech.

    This class is intentionally tiny and has no decision logic whatsoever.
    The "when" decisions live only in Cognitive (IdleMonologueBehavior etc.).

    It is one of the four main EventProcessors registered in bootstrap.py.
    """

    SUBSCRIPTIONS = {
        "monologue_prompt": "handle_event",
        "start_message": "handle_event",
    }

    def __init__(self, max_age_seconds: int = 30, memory_writer=None, event_bus=None):
        """
        Args:
            max_age_seconds: Events older than this are dropped as stale.
            memory_writer: Optional MemoryWriter (EventProcessor) for persistence.
            event_bus: The global EventBus used to publish the resulting ResponsePromptEvent.
        """
        super().__init__("autonomous prompt processor")
        self.max_age = timedelta(seconds=max_age_seconds)
        self.memory_writer = memory_writer
        self.event_bus = event_bus

    async def handle_event(self, event) -> None:
        """
        Main entry point for monologue-related events.

        Applies staleness filter, records the event in long-term memory,
        then delegates to _emit_prompt_request to produce the generation intent.
        """
        if await is_stale(event, self.max_age, self.logger, context="monologue"):
            return

        await forward_to_memory(event, self.memory_writer, self.logger)
        await self._emit_prompt_request(event)

    async def _emit_prompt_request(self, event) -> None:
        """
        Build a minimal ResponsePromptEvent from the raw monologue event and publish it.

        The prompt text (if present) is passed through unchanged; actual prompt
        assembly, RAG injection, and LLM calling happen downstream in the
        Generation layer.
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
