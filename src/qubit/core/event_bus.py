import asyncio
from dataclasses import dataclass
from typing import Callable, Dict, List
from src.qubit.utils.log_utils import get_logger
from src.qubit.core.events import Event

logger = get_logger(__name__)

class EventBus:
    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, handler: Callable):
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)

    async def publish(self, event: Event):
        if event.type in self.subscribers:
            for handler in self.subscribers[event.type]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event)
                    else:
                        handler(event)
                except Exception as e:
                    logger.error(f"Error in handler for {event.type}: {e}")

event_bus = EventBus() 

