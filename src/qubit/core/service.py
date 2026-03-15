
import asyncio
from src.utils.log_utils import get_logger

class Service:

    SUBSCRIPTIONS = {}

    def __init__(self, name):
        self.name = name
        self.event_bus = None
        self.logger = get_logger(name)

    async def _start(self, app):
        self.app = app
        self.event_bus = app.event_bus

        self.logger.info(f"Starting {self.name} — waiting for START command")

        await self._wait_for_start()

        self.logger.info(f"{self.name} started on frontend click")

        self._register_subscriptions()

        self.logger.info(f"{self.name} is running")

        self._worker_task = asyncio.create_task(self._run())

    async def _wait_for_start(self):
        await self.app.state.start.wait()

    async def _run(self):
        pass

    async def _stop(self):
        self.logger.info(f"Stopping {self.name}")
        if self._run:
            self._run.cancel()
            await asyncio.gather(self._run, return_exceptions=True)
            
    def _register_subscriptions(self):
        for event_type, handler_name in self.SUBSCRIPTIONS.items():
            handler = getattr(self, handler_name)
            self.event_bus.subscribe(event_type, handler)