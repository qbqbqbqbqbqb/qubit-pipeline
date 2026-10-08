"""Simple in-process event bus for async and sync handlers.

EventBus is instantiated once in bootstrap.py and attached to the App
instance as app.event_bus. All services and processors receive it from
there — nothing imports a module-level singleton.
"""

import asyncio
from typing import Callable, Dict, List

from src.qubit.utils.log_utils import get_logger
from src.qubit.core.events import Event

logger = get_logger(__name__)


class EventBus:
    """Publish/subscribe event bus for internal application events."""

    def __init__(self):
        """Initialise an empty subscriber registry."""
        self.subscribers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """Register a handler for a given event type."""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)

    async def publish(self, event: Event) -> None:
        """Dispatch an event to all registered handlers."""
        if event.type in self.subscribers:
            for handler in self.subscribers[event.type]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event)
                    else:
                        handler(event)
                except Exception as e:
                    logger.error("Error in handler for %s: %s", event.type, e)



