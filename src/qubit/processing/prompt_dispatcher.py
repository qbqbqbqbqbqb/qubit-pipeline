import asyncio
from datetime import datetime, timedelta, timezone
from src.qubit.prompting.modules.chat import chat_memory_module
from src.qubit.prompting.modules.reflection import reflection_memory_module
from src.qubit.core.service import Service
from src.qubit.models.async_hf_model_manager import AsyncHuggingFaceLLM
from src.utils.log_utils import get_logger

from src.qubit.core.event_bus import event_bus
from src.qubit.core.events import PromptAssemblyEvent, ResponseGeneratedEvent, ResponsePromptEvent
from src.qubit.prompting.prompt_assembler import PromptAssembler
from src.qubit.prompting.modules.core import core_system_module
from src.qubit.prompting.modules.input import input_module
from src.qubit.prompting.modules.personality import personality_module
from src.qubit.prompting.modules.stream_type import stream_type_module

logger = get_logger(__name__)

class PromptDispatcher(Service):
    SUBSCRIPTIONS = {
        "response_prompt": "enqueue",
    }
        
    def __init__(self, llm_client = AsyncHuggingFaceLLM, max_age_seconds=30):
        super().__init__("prompt_dispatcher")
        self.llm = llm_client
        self.queue = asyncio.Queue()
        self.system_mood = "energetic"
        self.system_tone = "casual and humorous"
        self.system_interaction = "high"
        self.max_age = timedelta(seconds=max_age_seconds)
        self._worker_task = None


    async def start(self, app):
        self.app = app
        logger.info("Starting PromptDispatcher")
        self._worker_task = asyncio.create_task(self._worker(app))
        await super().start(app)

    async def _worker(self, app):
        while not self.app.state.shutdown.is_set():
            if not self.app.state.start.is_set():
                await asyncio.sleep(1)
                continue
    
        while True:
            logger.info("queue eaten nomonomonomm")
            event: ResponsePromptEvent = await self.queue.get()
            try:
                if self._is_stale(event):
                    logger.info(f"Dropping stale prompt for {event.data.get('user')}: {event.prompt}")
                    continue

                response = await self._generate_response(event)

                logger.info(f"Response generated. Publishing {response}")
                await self._publish_response(event, response, app.event_bus)

            except Exception as e:
                logger.error(f"[LLM Worker] Error: {e}")
            finally:
                self.queue.task_done()

    async def stop(self):
        logger.info("Stopping PromptDispatcher")
        if self._worker_task:
            self._worker_task.cancel()
            await asyncio.gather(self._worker_task, return_exceptions=True)
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except asyncio.queues.QueueEmpty:
                break

    async def enqueue(self, event: ResponsePromptEvent):
        event_type = getattr(event, "type", "unknown")
        user = event.data.get("user", "unknown")
        prompt = getattr(event, "prompt", "")
        logger.info(f"[PromptDispatcher] enqueue called for {user} (type={event_type}): {prompt}")
        if not hasattr(event, "timestamp") or not event.timestamp:
            event.timestamp = datetime.utcnow()
        await self.queue.put(event)

    def update_system_personality(self, mood=None, tone=None, interaction_level=None):
        """Change the system module parameters at runtime."""
        if mood:
            self.system_mood = mood
        if tone:
            self.system_tone = tone
        if interaction_level:
            self.system_interaction = interaction_level

    
    async def _generate_with_retries(self, prompt, max_attempts=3):
        """
        Attempt to generate a response up to `max_attempts` times.
        """

        for attempt in range(1, max_attempts + 1):
            logger.info(f"[Attempt {attempt}] prompt: {prompt}")
            try:
                logger.info(f"[LLM] Generating response")
                response = await self.llm.generate_response(prompt)
                if response and response.strip():
                    logger.info(f"[Attempt {attempt}] response: {response}")
                    return response
                else:
                    logger.warning(f"[Attempt {attempt}] Empty response, retrying...")
            except Exception as e:
                logger.error(f"[Attempt {attempt}] LLM generation error: {e}")
            
            await asyncio.sleep(1)

        logger.error(f"All {max_attempts} attempts failed for prompt: {prompt}")
        return "Sorry, I couldn't generate a response right now."

    def _is_stale(self, event) -> bool:
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
        logger.info(f"[LLM] Generating response for {user}")

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
        await self.app.event_bus.publish(assembly_event)

        for injection in assembly_event.contributions:
            assembler.add(injection)

        assembler.add(input_module(prompt_text))
        for inj in assembly_event.contributions:
            logger.info(f"Injection ({inj.priority}): {inj.content[:80]}")
                    
        final_prompt = assembler.build()
        return await self._generate_with_retries(final_prompt, max_attempts=3)


    async def _publish_response(self, event: ResponsePromptEvent, response: str, event_bus):
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
        await event_bus.publish(generated_event)
        logger.info(f"Published {generated_event}")