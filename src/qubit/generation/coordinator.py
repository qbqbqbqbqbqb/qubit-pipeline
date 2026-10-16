"""
<summary>
GenerationCoordinator — single owner of the intent-to-LLM-response path.
</summary>
<remarks>
LAYER: Generation / Prompt Pipeline

Receives ResponsePromptEvent from the Cognitive layer (chat responses) or from
AutonomousPromptProcessor (monologues), assembles a complete prompt using
PromptAssembler and registered injection modules, calls the LLM via LLMService,
and publishes a ResponseGeneratedEvent.

Owns:
  - Input queue for pending generation requests
  - Staleness filtering (drop prompts older than max_age_seconds)
  - System personality state (mood, tone, interaction level)
  - Background _run loop that drains the queue

Retry logic is delegated to LLMService.generate_with_retries.

All other layers treat this as a black box: publish a ResponsePromptEvent,
later receive a ResponseGeneratedEvent.
</remarks>
"""

import asyncio
from datetime import datetime, timedelta, timezone

from config.config import MAX_GENERATION_ATTEMPTS
from src.qubit.processing.common import is_stale
from src.qubit.core.service import Service
from src.qubit.models.llm_service import LLMService
from src.qubit.core.events import PromptAssemblyEvent, ResponseGeneratedEvent, ResponsePromptEvent
from src.qubit.prompting.prompt_assembler import PromptAssembler
from src.qubit.prompting.modules.core import core_system_module
from src.qubit.prompting.modules.input import input_module
from src.qubit.prompting.modules.personality import personality_module
from src.qubit.prompting.modules.stream_type import stream_type_module


class GenerationCoordinator(Service):
    """
    <summary>
    Service that queues generation intents, assembles full prompts, and calls the LLM.
    </summary>
    """

    SUBSCRIPTIONS = {
        "response_prompt": "enqueue",
    }

    def __init__(self, llm_service: LLMService, max_age_seconds: int = 30, main_profile: str = "main"):
        """
        <summary>Initialise the coordinator with an LLM service and queue settings.</summary>
        <param name="llm_service">The central LLM orchestrator (provides generate and generate_with_retries).</param>
        <param name="max_age_seconds">Prompts older than this are dropped as stale.</param>
        <param name="main_profile">Default LLM profile name to pass to generate().</param>
        """
        super().__init__("generation_coordinator")
        self.llm_service = llm_service
        self.main_profile = main_profile
        self.queue: asyncio.Queue = asyncio.Queue()
        self.system_mood = "energetic"
        self.system_tone = "casual and humorous"
        self.system_interaction = "high"
        self.max_age = timedelta(seconds=max_age_seconds)

        # Static injections: built once at startup, reused on every generation call.
        # personality_module and input_module are NOT cached — they depend on
        # runtime state (mood/tone) and per-request input respectively.
        self._core_injection = core_system_module()
        self._stream_type_injection = stream_type_module()

    async def _run(self) -> None:
        """
        <summary>
        Background loop that waits for the app start signal then drains the queue,
        generating one response per item.
        </summary>
        """
        while not self.app.state.shutdown.is_set():
            if not self.app.state.start.is_set():
                await asyncio.sleep(1)
                continue

            while not self.app.state.shutdown.is_set():
                event: ResponsePromptEvent = await self.queue.get()
                try:
                    if await self._is_stale(event):
                        self.logger.info(
                            "[_run] Dropping stale prompt for %s: %s",
                            event.data.get("user"), event.prompt,
                        )
                        continue

                    response = await self._generate_response(event)
                    self.logger.info("[_run] Response generated. Publishing: %s", response)
                    await self._publish_response(event, response)

                except Exception as e:
                    self.logger.error("[_run] Error: %s", e)
                finally:
                    self.queue.task_done()

    async def stop(self) -> None:
        """
        <summary>Drain the queue without processing, then stop the worker task.</summary>
        """
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except asyncio.queues.QueueEmpty:
                break
        await super().stop()

    async def enqueue(self, event: ResponsePromptEvent) -> None:
        """
        <summary>
        Receive a generation intent and place it on the queue for the background loop.
        Timestamps any event missing one before queuing.
        </summary>
        <param name="event">The ResponsePromptEvent to enqueue.</param>
        """
        event_type = getattr(event, "type", "unknown")
        user = event.data.get("user", "unknown")
        prompt = getattr(event, "prompt", "")
        self.logger.info("[enqueue] Queued for %s (type=%s): %s", user, event_type, prompt)
        if not getattr(event, "timestamp", None):
            event.timestamp = datetime.now(timezone.utc).isoformat()
        await self.queue.put(event)

    def update_system_personality(
        self,
        mood: str | None = None,
        tone: str | None = None,
        interaction_level: str | None = None,
    ) -> None:
        """
        <summary>
        Runtime hook to adjust personality injection parameters without restart.
        Values are passed to personality_module on the next generation call.
        </summary>
        <param name="mood">New mood string, or None to leave unchanged.</param>
        <param name="tone">New tone string, or None to leave unchanged.</param>
        <param name="interaction_level">New interaction level string, or None to leave unchanged.</param>
        """
        if mood:
            self.system_mood = mood
        if tone:
            self.system_tone = tone
        if interaction_level:
            self.system_interaction = interaction_level

    async def _is_stale(self, event: object) -> bool:
        """
        <summary>Return True if the event's timestamp is older than max_age.</summary>
        <remarks>Delegates to processing.common.is_stale — the single staleness
        implementation shared across all processors.</remarks>
        <param name="event">The event to check.</param>
        <returns>True if the event should be dropped as stale.</returns>
        """
        return await is_stale(event, self.max_age, self.logger, context="generation")

    async def _generate_response(self, event: ResponsePromptEvent) -> str:
        """
        <summary>
        Assemble the full prompt using PromptAssembler and all registered injections,
        then call generate_with_retries.
        </summary>
        <param name="event">The ResponsePromptEvent containing the user and prompt text.</param>
        <returns>The generated response string.</returns>
        """
        user = event.data.get("user")
        prompt_text = event.prompt
        self.logger.info("[_generate_response] Assembling prompt for %s", user)

        assembler = PromptAssembler()
        assembler.add(self._core_injection)
        assembler.add(personality_module(
            mood=self.system_mood,
            tone=self.system_tone,
            interaction_level=self.system_interaction,
        ))
        assembler.add(self._stream_type_injection)

        assembly_event = PromptAssemblyEvent(
            type="prompt_assembly",
            timestamp=datetime.now(timezone.utc).isoformat(),
            data={},
            assembler=assembler,
            user=user,
            prompt_text=prompt_text,
        )
        await self.event_bus.publish(assembly_event)

        for injection in assembly_event.contributions:
            assembler.add(injection)

        assembler.add(input_module(prompt_text))
        for inj in assembly_event.contributions:
            self.logger.info("[_generate_response] Injection (%s): %s", inj.priority, inj.content[:80])

        final_prompt = assembler.build()
        return await self.llm_service.generate_with_retries(
            profile=self.main_profile,
            input=final_prompt,
            max_attempts=MAX_GENERATION_ATTEMPTS,
        )

    async def _publish_response(self, event: ResponsePromptEvent, response: str) -> None:
        """
        <summary>Construct and publish a ResponseGeneratedEvent for the Output layer.</summary>
        <param name="event">The originating ResponsePromptEvent.</param>
        <param name="response">The generated response text.</param>
        """
        user = event.data.get("user")
        generated_event = ResponseGeneratedEvent(
            type="response_generated",
            source=event.source,
            timestamp=datetime.now(timezone.utc).isoformat(),
            data={
                "user": user,
                "source": event.source,
                "prompt": event.prompt,
                "response": response,
            },
            prompt=event.prompt,
            response=response,
        )
        await self.event_bus.publish(generated_event)
        self.logger.info("[_publish_response] Published %s", generated_event)
