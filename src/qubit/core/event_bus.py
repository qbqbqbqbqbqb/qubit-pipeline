"""
<summary>
Simple in-process event bus supporting both async and sync handlers.
Instantiated once in bootstrap.py and attached to the App instance as app.event_bus.
Nothing imports a module-level singleton — all services receive it from App.
</summary>
"""

import asyncio
from typing import Callable, Dict, List

from src.qubit.utils.log_utils import get_logger
from src.qubit.core.events import Event

logger = get_logger(__name__)


class EventBus:
    """
    <summary>
    Publish/subscribe event bus for internal application events.
    </summary>
    """

    def __init__(self):
        """
        <summary>Initialise an empty subscriber registry.</summary>
        """
        self.subscribers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """
        <summary>Register a handler for a given event type.</summary>
        <param name="event_type">The event type string to subscribe to.</param>
        <param name="handler">The callable to invoke when the event is published.</param>
        """
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)

    async def publish(self, event: Event) -> None:
        """
        <summary>Dispatch an event to all registered handlers.</summary>
        <param name="event">The Event instance to publish.</param>
        """
        if event.type in self.subscribers:
            for handler in self.subscribers[event.type]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event)
                    else:
                        handler(event)
                except Exception as e:
                    logger.error("Error in handler for %s: %s", event.type, e)
