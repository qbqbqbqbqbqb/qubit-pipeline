from datetime import datetime, timedelta, timezone
from src.qubit.core.service import Service
from src.qubit.core.event_bus import event_bus
from src.qubit.utils.message_tracker import MessageTracker
from src.utils.log_utils import get_logger

logger = get_logger(__name__)
class MonologueInputHandler(Service):
    SUBSCRIPTIONS = {
        "monologue_prompt": "handle_event",
    }
        
    def __init__(self, max_age_seconds=30, prompt_handler=None):
        super().__init__(" monologue input handler")
        self.max_age = timedelta(seconds=max_age_seconds)
        self.message_tracker = MessageTracker()
        self.prompt_handler = prompt_handler

    async def start(self, app):
        logger.info("Starting MonologueInputHandlerService")
        self.event_bus = app.event_bus
        await super().start(app)


    async def stop(self):
        logger.info("Stopping MonologueInputHandlerService")

    async def handle_event(self, event):
        text = event.data.get("text", "").lower().strip()

        ts = getattr(event, "timestamp", datetime.now(timezone.utc))
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        if datetime.now(timezone.utc) - ts > self.max_age:
            logger.debug(f"Dropping stale monologue: {text}") 
            return

        if self.prompt_handler and event.type in self.prompt_handler.builders:
            builder = self.prompt_handler.builders[event.type]
            prompt_event = builder(event)
            await self.prompt_handler.dispatcher.enqueue(prompt_event)