import asyncio
import random
from datetime import datetime, timezone

from src.qubit.core.service import Service
from src.qubit.core.events import MonologueEvent

class MonologueScheduler(Service):

    SUBSCRIPTIONS = {
        "twitch_chat_processed": "_notify_activity",
    }

    def __init__(self, dispatcher,  llm, inactivity_timeout=120):
        super().__init__("monologue scheduler")
        self.dispatcher = dispatcher
        self.llm = llm
        self.inactivity_timeout = inactivity_timeout
        self.last_activity = datetime.now(timezone.utc)

    async def start(self, app) -> None:
        await super().start(app)

    async def stop(self) -> None:
        await super().stop()

    async def _run(self) -> None:
        await super()._run()
        while not self.app.state.shutdown.is_set():

            monologue_enabled = self.app.state.features.get("monologue", True)
            self.logger.debug("[_run] MonologueScheduler loop - start: %s, " \
            "monologue_enabled: %s, last_activity: %s",
                              self.app.state.start.is_set(),
                              monologue_enabled,
                              self.last_activity)
            if not self.app.state.start.is_set() or not monologue_enabled:
                await asyncio.sleep(1)
                continue

            if monologue_enabled:
                elapsed = (datetime.now(timezone.utc) - self.last_activity).total_seconds()
                if elapsed >= self.inactivity_timeout:
                    self.logger.info("[_run] Inactivity timeout reached, generating monologue")
                    await self._generate_monologue()
                    self.last_activity = datetime.now(timezone.utc)
                await asyncio.sleep(5)


    async def _notify_activity(self, _event)  -> None:
        self.logger.info("[_notify_activity] Chat processed")
        self.last_activity = datetime.now(timezone.utc)

    async def _generate_monologue(self)  -> None:
        self.logger.info("[_generate_monologue] Monologue generated")
        topic = await self._get_topic_for_monologue()
        prompt = f"Monologue about {topic}, in character as Qubit."

        event = MonologueEvent(
            type="monologue_prompt",
            user="system",
            timestamp=datetime.now(timezone.utc).isoformat(),
            data={"user": "system", "topic": topic, "prompt": prompt},
            prompt=prompt
        )

        await self._publish_event_to_broker(event)

    async def _get_topic_for_monologue(self) -> str:
        topics = [
                    "a funny story about AI",
                    "an interesting Twitch fact",
                    "a quirky joke",
                    "motivational advice",
                    "a short adventure tale"
                ]
        return random.choice(topics)


    async def _publish_event_to_broker(self, event) -> None:
        if self.event_bus:
            await self.event_bus.publish(event)
            self.logger.info("[_publish_event_to_broker] Published event: %s", event)
