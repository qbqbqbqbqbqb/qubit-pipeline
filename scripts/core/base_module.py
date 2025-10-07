import asyncio
from scripts.utils.log_utils import get_logger

class BaseModule:
    def __init__(self, name, logger=None):
        self.name = name
        self.logger = get_logger(name)
        self._running = False
        self._task = None

    async def start(self):
        """Start the module event loop or main task."""
        self.logger.info(f"{self.name} starting...")
        self._running = True
        self._task = asyncio.create_task(self.run())

    async def run(self):
        """Override in subclass: main loop or work."""
        raise NotImplementedError

    async def stop(self):
        """Stop the module and clean up."""
        self.logger.info(f"{self.name} stopping...")
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
