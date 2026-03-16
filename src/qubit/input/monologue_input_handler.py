#again, does this need to be a service?
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
        
    def __init__(self, max_age_seconds=30, prompt_handler=None, memory_handler=None):
        super().__init__(" monologue input handler")
        self.max_age = timedelta(seconds=max_age_seconds)
        self.message_tracker = MessageTracker()
        self.prompt_handler = prompt_handler
        self.memory_handler = memory_handler
        
    async def start(self, app) -> None:
        await super().start(app)


    async def stop(self) -> None:
        await super().stop()

    # TODO: consolidate redundant methods btwn input handlers here later
    async def handle_event(self, event) -> None:
        text = event.data.get("text", "").lower().strip()

        await self._check_stale_message(event, text)

        await self._handle_memory_event(event)
            
        await self._enqueue_event_prompt(event)

    async def _check_stale_message(self, event, text) -> bool:
        ts = getattr(event, "timestamp", datetime.now(timezone.utc))
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        if datetime.now(timezone.utc) - ts > self.max_age:
            self.logger.debug(f"Dropping stale monologue: {text}") 
            return True
        return False
    
    # i forgot why i made this different to chat handling
    # TODO: check if logic can be merged
    async def _enqueue_event_prompt(self, event) -> None:
        if self.prompt_handler and event.type in self.prompt_handler.builders:
            builder = self.prompt_handler.builders[event.type]
            prompt_event = builder(event)
            await self.prompt_handler.dispatcher.enqueue(prompt_event)


    async def _handle_memory_event(self, event) -> None:
        if self.memory_handler:
            self.memory_handler.handle_event(event)