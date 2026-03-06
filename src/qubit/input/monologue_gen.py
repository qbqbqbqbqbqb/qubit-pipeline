import asyncio
from datetime import datetime, timezone

from src.qubit.core.event_bus import event_bus
from src.qubit.core.events import MonologueEvent, ResponsePromptEvent
from src.qubit.utils.log_utils import get_logger

logger = get_logger(__name__)

class MonologueScheduler:
    def __init__(self, dispatcher, inactivity_timeout=120, monologue_enabled=None):
        self.dispatcher = dispatcher
        self.inactivity_timeout = inactivity_timeout
        self.last_activity = datetime.now(timezone.utc)
        self.monologue_enabled = monologue_enabled
        self.task = asyncio.create_task(self._loop())

    def notify_activity(self, event=None):
        logger.info("Chat processed")
        self.last_activity = datetime.now(timezone.utc)

    async def _loop(self):
        while self.monologue_enabled.is_set(): 
            elapsed = (datetime.now(timezone.utc) - self.last_activity).total_seconds()
            if elapsed >= self.inactivity_timeout:
                logger.info("Inactivity timeout reached, generating monologue")
                await self.generate_monologue()
                self.last_activity = datetime.now(timezone.utc)
            await asyncio.sleep(5)

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