from scripts.core.base_module import BaseModule
from scripts.utils.log_utils import get_logger

class ModuleManager:
    def __init__(self, logger=None):
        self.modules = {}
        self.logger = get_logger("ModuleManager")

    async def start_all(self):
        self.logger.info("Starting all modules...")
        for name, module in self.modules.items():
            await module.start()

    async def stop_all(self):
        self.logger.info("Stopping all modules...")
        for name, module in self.modules.items():
            await module.stop()

    def register(self, module: BaseModule):
        self.modules[module.name] = module
        self.logger.info(f"Registered module: {module.name}")
