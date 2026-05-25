"""
Generation Coordinator — the single owner of the "decision → LLM call → response" path.

LAYER: Generation / Prompt Pipeline (see ARCHITECTURE.md)

This Service is the canonical place where:
- High-level intents arrive (response_prompt from Cognitive, monologue_prompt from processors)
- The full prompt is assembled (PromptAssembler + core + personality + stream type + memory RAG via prompt_assembly event)
- The LLM is called (via LLMService with the chosen profile)
- The final ResponseGeneratedEvent is published

It owns the request queue, staleness filtering for prompts, retry logic, and
system personality knobs (mood/tone/interaction).

All other layers should treat this as a black box: "I published an intent event,
later a response_generated event will appear."

Previous name: PromptDispatcher (renamed for clarity during 2026 SoC refactor).
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
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
    The single owner of the "high-level intent → full prompt → LLM call → ResponseGeneratedEvent" path.

    This Service is the canonical choke point for all text generation in the system.
    It receives ResponsePromptEvent (from Cognitive for chat responses, or from
    AutonomousPromptProcessor for monologues), assembles the complete prompt using
    the PromptAssembler + all injection modules + memory RAG, calls the LLM via
    LLMService, and publishes the final response event.

    It owns:
    - The input queue for pending generation requests
    - Staleness filtering (drop old prompts)
    - Retry logic for LLM calls
    - System personality state (mood, tone, interaction level)
    - The 5s background loop that drains the queue

    All other layers treat this as a black box.
    """

    SUBSCRIPTIONS = {
        "response_prompt": "enqueue",
    }

    def __init__(self, llm_service: LLMService, max_age_seconds=30, main_profile: str = "main"):
        """
        Args:
            llm_service: The central LLM orchestrator (provides generate_with_retries).
            max_age_seconds: Prompts older than this are dropped as stale.
            main_profile: Default LLM profile to use for generation.
        """
        super().__init__("generation_coordinator")
        self.llm_service = llm_service
        self.main_profile = main_profile
        self.queue = asyncio.Queue()
        self.system_mood = "energetic"
        self.system_tone = "casual and humorous"
        self.system_interaction = "high"
        self.max_age = timedelta(seconds=max_age_seconds)

    async def start(self, app):
        await super().start(app)

    async def _run(self) -> None:
        await super()._run()
        while not self.app.state.shutdown.is_set():
            if not self.app.state.start.is_set():
                await asyncio.sleep(1)
                continue

            while True:
                event: ResponsePromptEvent = await self.queue.get()
                try:
                    if self._is_stale(event):
                        self.logger.info("[_run]Dropping stale prompt for %s: %s", event.data.get('user'), event.prompt)
                        continue

                    response = await self._generate_response(event)

                    self.logger.info("[_run]Response generated. Publishing: %s", response)
                    await self._publish_response(event, response)

                except Exception as e:
                    self.logger.error("[_run] Error: %s", e)
                finally:
                    self.queue.task_done()

    async def stop(self) -> None:
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except asyncio.queues.QueueEmpty:
                break
        await super().stop()

    async def enqueue(self, event: ResponsePromptEvent):
        """
        Receive a high-level generation intent from Cognitive or Autonomous layer.

        The event is queued for processing in the background _run loop.
        Staleness and timestamp normalization are handled here.
        """
        event_type = getattr(event, "type", "unknown")
        user = event.data.get("user", "unknown")
        prompt = getattr(event, "prompt", "")
        self.logger.info("[enqueue] enqueue called for %s (type=%s): %s", user, event_type, prompt)
        if not hasattr(event, "timestamp") or not event.timestamp:
            event.timestamp = datetime.now(timezone.utc)
        await self.queue.put(event)

    def update_system_personality(self, mood=None, tone=None, interaction_level=None) -> None:
        """
        Runtime hook to adjust the personality injection modules.

        Called from frontend or tests to change mood/tone without restart.
        These values are injected into every prompt via the personality_module.
        """
        if mood:
            self.system_mood = mood
        if tone:
            self.system_tone = tone
        if interaction_level:
            self.system_interaction = interaction_level


    async def generate_with_retries(self, prompt, max_attempts=3) -> Any:
        """
        Attempt to generate a response up to `max_attempts` times using the main profile.
        """
        for attempt in range(1, max_attempts + 1):
            self.logger.info("[_generate_with_retries][Attempt %s] prompt: %s", attempt, prompt)
            try:
                self.logger.info("[_generate_with_retries] Generating response")
                response = await self.llm_service.generate_with_retries(
                    profile=self.main_profile,
                    input=prompt,
                    max_attempts=1,  # we handle retries here
                )
                if response and response.strip():
                    self.logger.info("[_generate_with_retries][Attempt %s] response: %s", attempt, response)
                    return response
                self.logger.warning("[_generate_with_retries][Attempt %s] Empty response, retrying...", attempt)
            except Exception as e:  # pylint: disable=broad-exception-caught
                self.logger.error("[_generate_with_retries] [Attempt %s] LLM generation error: %s", attempt, e)

            await asyncio.sleep(1)

        self.logger.error("[_generate_with_retries] All %s attempts failed for prompt: %s", max_attempts, prompt)
        return "Sorry, I couldn't generate a response right now."

    def _is_stale(self, event: Any) -> bool:
        ts = getattr(event, "timestamp", None)
        if ts is None:
            ts_dt = datetime.now(timezone.utc)
        elif isinstance(ts, str):
            ts_dt = datetime.fromisoformat(ts)
        else:
            ts_dt = ts

        return datetime.now(timezone.utc) - ts_dt > self.max_age


    async def _generate_response(self, event: ResponsePromptEvent) -> str:
        user = event.data.get("user")
        prompt_text = event.prompt
        self.logger.info("[_generate_response] Generating response for %s", user)

        assembler = PromptAssembler()
        assembler.add(core_system_module())
        assembler.add(personality_module(
            mood=self.system_mood,
            tone=self.system_tone,
            interaction_level=self.system_interaction))
        assembler.add(stream_type_module())

        assembly_event = PromptAssemblyEvent(
            type="prompt_assembly",
            timestamp=datetime.now(timezone.utc).isoformat(),
            data={},
            assembler=assembler,
            user=user,
            prompt_text=prompt_text
        )
        await self.event_bus.publish(assembly_event)

        for injection in assembly_event.contributions:
            assembler.add(injection)

        assembler.add(input_module(prompt_text))
        for inj in assembly_event.contributions:
            self.logger.info("[_generate_response] Injection (%s): %s", inj.priority, inj.content[:80])

        final_prompt = assembler.build()
        return await self.generate_with_retries(final_prompt, max_attempts=3)


    async def _publish_response(self, event: ResponsePromptEvent, response: str) -> None:
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
            response=response
        )
        await self.event_bus.publish(generated_event)
        self.logger.info("[_publish_response] Published %s", generated_event)
