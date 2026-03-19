import asyncio
from src.utils.log_utils import get_logger

class Service:

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
            self.event_bus.subscribe(event_type, handler)
