import asyncio
from datetime import datetime, timezone


from src.qubit.core.service import Service
from src.qubit.core.event_bus import event_bus
from src.qubit.core.events import MonologueEvent
from src.utils.log_utils import get_logger

logger = get_logger(__name__)

class MonologueScheduler(Service):
    def __init__(self, dispatcher,  llm, inactivity_timeout=120):
        super().__init__("monologue scheduler")
        self.dispatcher = dispatcher
        self.llm = llm
        self.inactivity_timeout = inactivity_timeout
        self.last_activity = datetime.now(timezone.utc)

    async def start(self, app):
        logger.info("Starting MonologueScheduler")
        self.event_bus = app.event_bus
        self._worker_task = asyncio.create_task(self._worker(app))
        await super().start(app)

    async def stop(self):
        logger.info("Stopping MonologueScheduler")
        if self._worker_task:
            self._worker_task.cancel()
            await asyncio.gather(self._worker_task, return_exceptions=True)

    async def _worker(self, app):
        app.event_bus.subscribe("twitch_chat_processed", self.notify_activity)

        monologue_enabled = app.state.features.get("monologue", True)

        while monologue_enabled: 
            elapsed = (datetime.now(timezone.utc) - self.last_activity).total_seconds()
            if elapsed >= self.inactivity_timeout:
                logger.info("Inactivity timeout reached, generating monologue")
                await self.generate_monologue()
                self.last_activity = datetime.now(timezone.utc)
            await asyncio.sleep(5)

    def notify_activity(self, event=None):
        logger.info("Chat processed")
        self.last_activity = datetime.now(timezone.utc)

    async def generate_monologue(self):
        logger.info("Monologue generated")
        import random
        topics = [
            "a funny story about AI",
            "an interesting Twitch fact",
            "a quirky joke",
            "motivational advice",
            "a short adventure tale"
        ]
        topic = random.choice(topics)
        prompt = f"Monologue about {topic}, in character as Qubit."
    
        event = MonologueEvent(
            type="monologue_prompt",
            user="system",
            timestamp=datetime.now(timezone.utc).isoformat(),
            data={"user": "system", "topic": topic, "prompt": prompt},
            prompt=prompt
        )

        await event_bus.publish(event)
        logger.info(f"Published {event}")