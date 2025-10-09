import asyncio
from scripts.core.base_module import BaseModule
from scripts.managers.model_manager import ModelManager
from scripts.utils.log_utils import get_logger

class ModelModule(BaseModule):
    def __init__(self, model_manager: ModelManager, signals):
        super().__init__("ModelModule", logger=get_logger("ModelModule"))
        self.model_manager = model_manager
        self.signals = signals 

    async def run(self):
        self.logger.info("ModelModule is idle and ready.")
        try:
            while self._running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            self.logger.info("ModelModule run task cancelled.")
            raise

    async def stop(self):
        self.logger.info("ModelModule shutting down.")
        await super().stop()
