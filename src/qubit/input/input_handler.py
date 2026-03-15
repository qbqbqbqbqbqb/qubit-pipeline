#same thing here as in input moderation
# does this still need to be a service when i removed the main loop?
from datetime import datetime, timedelta, timezone
from src.qubit.core.service import Service
from src.qubit.utils.message_tracker import MessageTracker

class InputHandler(Service):

    SUBSCRIPTIONS = {
        "twitch_chat_processed": "handle_event",
        "twitch_subscription_processed": "handle_event",
        "twitch_raid_processed": "handle_event",
        "twitch_follow_processed": "handle_event",
    }
        
    def __init__(self, max_age_seconds=30, prompt_handler=None, memory_handler=None):
        super().__init__("input_handler")
        self.max_age = timedelta(seconds=max_age_seconds)
        self.message_tracker = MessageTracker()
        self.prompt_handler = prompt_handler
        self.memory_handler = memory_handler

    async def _start(self, app) -> None:
        await super()._start(app)    

    async def _stop(self) -> None:
        await super()._stop()

    async def handle_event(self, event) -> None:
        self.logger.info("Handling event in InputHandlerService")
        text = event.data.get("text", "").lower().strip()

        if await self._check_repeated_message(text):
            return
        
        await self._add_message_to_tracker(text)
        
        if await self._check_stale_message(event, text):
            return

        built_input = await self._build_event_prompt(event)

        await self._handle_memory_event(event)

        await self._queue_built_event(built_input)


    async def _check_repeated_message(self, text) -> bool:
        if self.message_tracker.is_repeated(text):
            self.logger.debug(f"Dropped repeated message: {text}")
            return True
        return False
    

    async def _add_message_to_tracker(self, text) -> None:
        if self.message_tracker:
            self.message_tracker.add_message(text)


    async def _check_stale_message(self, event, text) -> bool:
        ts = getattr(event, "timestamp", datetime.now(timezone.utc))
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        if datetime.now(timezone.utc) - ts > self.max_age:
            self.logger.debug(f"Dropping stale message: {text}") 
            return True
        return False
    

    async def _build_event_prompt(self, event) -> None:
        if self.prompt_handler and event.type in self.prompt_handler.builders:
            return await self.prompt_handler.handle_event(event)


    async def _handle_memory_event(self, event) -> None:
        if self.memory_handler:
            self.memory_handler.handle_event(event)


    async def _queue_built_event(self, built_input) -> None:
        if self.prompt_handler:
            await self.prompt_handler.queue_event(built_input)