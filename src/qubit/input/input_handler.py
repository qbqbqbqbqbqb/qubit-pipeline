import asyncio
from datetime import datetime, timedelta, timezone
from src.qubit.core.service import Service
from src.qubit.core.event_bus import event_bus
from src.qubit.utils.message_tracker import MessageTracker
from src.utils.log_utils import get_logger

logger = get_logger(__name__)
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

    async def start(self, app):
        logger.info("Starting InputHandlerService")
        self.event_bus = app.event_bus
        await super().start(app)    

    async def stop(self):
        logger.info("Stopping InputHandlerService")

    async def handle_event(self, event):
        logger.info("Handling event in InputHandlerService")
        text = event.data.get("text", "").lower().strip()

        if self.message_tracker.is_repeated(text):
            logger.debug(f"Dropped repeated message: {text}")
            return
        self.message_tracker.add_message(text)

        ts = getattr(event, "timestamp", datetime.now(timezone.utc))
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        if datetime.now(timezone.utc) - ts > self.max_age:
            logger.debug(f"Dropping stale message: {text}") 
            return
        
        if self.prompt_handler and event.type in self.prompt_handler.builders:
            built_input = await self.prompt_handler.handle_event(event)

        self.memory_handler.handle_event(event)

        if self.prompt_handler:
            await self.prompt_handler.queue_event(built_input)

