"""
Core Service base class.

CONTRACT (see ARCHITECTURE.md):
- Subclass Service when your component needs its own long-running loop,
  owns a queue, manages a connection, or performs background work.
- Services participate in the standard start/stop lifecycle and get a _run() loop.
- Use EventProcessor instead for pure reactors that only transform or react to events
  with no independent loop (moderation, dedup, memory writes, etc.).

This is the framework boundary. Domain logic belongs in the layers above.
"""

import asyncio
from src.utils.log_utils import get_logger


class Service:
    """
    Base class for components that own a lifecycle + optional background work.

    Responsibilities of a Service:
    - Owns its own _run() loop (started after frontend "start" signal)
    - Manages subscriptions via the SUBSCRIPTIONS class attr
    - Participates in graceful shutdown

    Do NOT put heavy domain decision logic or prompt building here.
    Those belong in Cognitive, Generation, Memory, or Output layers.
    """

    SUBSCRIPTIONS = {}

    def __init__(self, name):
        self.name = name
        self.app = None
        self.event_bus = None
        self.logger = get_logger(name)
        self._worker_task = None

    async def start(self, app):
        self.app = app
        self.event_bus = app.event_bus

        self.logger.info("[start] Starting %s — waiting for START command", self.name)

        self._register_subscriptions()

        await self._wait_for_start()

        self.logger.info("[start] %s started on frontend click", self.name)

        self.logger.info("[_register_subscriptions] %s has registered subscriptions: %s", self.name, list(self.SUBSCRIPTIONS.keys()))

        self._worker_task = asyncio.create_task(self._run())

    async def _wait_for_start(self):
        await self.app.state.start.wait()

    async def _run(self):
        self.logger.info("[_run] %s main loop is running", self.name)

    async def stop(self):
        self.logger.info("[stop] Stopping %s", self.name)
        if self._worker_task:
            self._worker_task.cancel()
            await asyncio.gather(self._worker_task, return_exceptions=True)

    def _register_subscriptions(self):
        for event_type, handler_name in self.SUBSCRIPTIONS.items():
            handler = getattr(self, handler_name)
            if handler:
                self.event_bus.subscribe(event_type, handler)
                self.logger.info(f"[{self.name}] Registered subscription: {event_type}")
            else:
                self.logger.warning(f"[{self.name}] Handler {handler_name} not found")
