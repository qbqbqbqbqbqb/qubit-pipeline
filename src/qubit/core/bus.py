import asyncio
from collections import defaultdict
from typing import Awaitable, Callable

from .events import Event, EventType


class EventBus:
    def __init__(self):
        self._handlers: dict[EventType, list[Callable[[Event], Awaitable[None]]]] = defaultdict(list)
        self._queue = asyncio.Queue()

    def subscribe(self, event_type: EventType, handler: Callable[[Event], Awaitable[None]]):
        self._handlers[event_type].append(handler)

    async def publish(self, event: Event):
        await self._queue.put(event)

    async def run(self):
        while True:
            event = await self._queue.get()
            try:
                for handler in self._handlers.get(event.type, []):
                    asyncio.create_task(handler(event))
            except Exception as exc:
                print(f"Event bus error on {event.type}: {exc}")
            finally:
                self._queue.task_done()