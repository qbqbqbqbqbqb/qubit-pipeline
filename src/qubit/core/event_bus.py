"""
Central publish/subscribe event bus for the entire application.

The EventBus is the backbone of the event-driven architecture. All major
components communicate by publishing and subscribing to typed events rather
than calling each other directly.

Design principles:
- Decoupled communication between layers
- Single global instance (event_bus) is used throughout the application
- Supports both sync and async handlers
- Errors in individual handlers are logged but do not crash the publisher

Typical usage:
- Services and Processors declare SUBSCRIPTIONS
- High-level components (Cognitive, Generation) publish intent events
- Lower layers react via registered handlers
"""

import asyncio
from typing import Callable, Dict, List

from src.utils.log_utils import get_logger
from src.qubit.core.events import Event

logger = get_logger(__name__)


class EventBus:
    """
    Simple in-memory event bus supporting pub/sub with async-aware dispatch.

    Maintains a mapping from event type string to list of handler callables.
    When an event is published, all registered handlers for that type are invoked.
    Async handlers are awaited; sync handlers are called directly.
    """

    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """
        Register a handler for a specific event type.

        Multiple handlers may be registered for the same event type.
        Handlers are called in the order they were subscribed.
        """
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)

    async def publish(self, event: Event) -> None:
        """
        Dispatch an event to all registered handlers for its type.

        Async handlers are awaited sequentially.
        Exceptions in handlers are caught, logged, and do not stop other handlers.
        """
        if event.type in self.subscribers:
            for handler in self.subscribers[event.type]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event)
                    else:
                        handler(event)
                except Exception as e:
                    logger.error(f"Error in handler for {event.type}: {e}")


# Global singleton used by the entire application
event_bus = EventBus() 

