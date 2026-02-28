from datetime import datetime, timedelta, timezone
from src.qubit.core.event_bus import event_bus
from src.qubit.core.events import ResponsePromptEvent
from src.qubit.utils.message_tracker import MessageTracker
from src.qubit.utils.log_utils import get_logger

logger = get_logger(__name__)
class InputHandler:
    def __init__(self, max_age_seconds=30, prompt_handler=None):
        self.max_age = timedelta(seconds=max_age_seconds)
        self.message_tracker = MessageTracker()
        self.prompt_handler = prompt_handler

    async def handle_event(self, event):
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
            builder = self.prompt_handler.builders[event.type]
            prompt_event = builder(event)
            await self.prompt_handler.dispatcher.enqueue(prompt_event)