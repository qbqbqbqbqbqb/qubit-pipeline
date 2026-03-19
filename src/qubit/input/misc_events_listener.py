#input file for misc events sent from frontend
# e.g. start event msg to send to llm gen
# subvscribe to start event
# on start ecvent send prompt 

from datetime import datetime, timezone
import random
from typing import Any
from src.qubit.core.events import MiscInputEvent
from src.qubit.core.service import Service

class MiscEventsListener(Service):


    SUBSCRIPTIONS = {
        "bot_started": "handle_event",
    }

    def __init__(self):
        super().__init__("MiscEventsListener")

    async def start(self, app) -> None:
        await super().start(app)

    async def stop(self) -> None:
        await super().stop()

    async def handle_event(self: Any, event: Any) -> None:
        handled_event = None
        if event.type == "bot_started":
            self.logger.info("[handle_event] Handling bot_started event in MiscEventsListener")
            handled_event = await self._generate_start_message_event(event)
        
        await self.event_bus.publish(handled_event)

    async def _generate_start_message_event(self: Any, event: Any)  -> None:
        prompt = await self._get_start_prompt()

        handled_event = MiscInputEvent(
            type="start_message",
            user="system",
            data={"user": "system", "start_message": prompt, "actual_start_time": event.timestamp},
            prompt=prompt,
            timestamp = datetime.now(timezone.utc).isoformat()
        )

        return handled_event

    async def _get_start_prompt(self) -> str:
        intros = [
            "Welcome to the stream! I'm Qubit, your friendly AI companion. Let's have some fun together!",
            "Hey there! Qubit here, ready to dive into some awesome content. Thanks for joining the stream!",
            "Hello everyone! I'm Qubit, your AI sidekick. Let's make this stream unforgettable!",
            "Hi folks! Qubit here, excited to kick off the stream. Let's explore some cool topics together!",
                ]
        
        prompt = f"You just started the stream. Say something to welcome the audience like {random.choice(intros)} to kick things off, in character as Qubit."
        return prompt


    async def _publish_event_to_broker(self, event) -> None:
        if self.event_bus:
            await self.event_bus.publish(event)
            self.logger.info("[_publish_event_to_broker] Published event: %s", event)
