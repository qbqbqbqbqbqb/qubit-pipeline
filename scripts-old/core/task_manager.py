import asyncio

from scripts.utils.log_utils import get_logger
logger = get_logger("TaskManager")

class TaskManager:
    """
    Manages async task lifecycle for the VTuber bot.

    Provides centralized task creation, tracking, and cancellation
    to ensure clean shutdown of all background operations.
    """

    def __init__(self, settings, logger):
        self.settings = settings
        self.logger = logger
        self.tasks = []

    def add_task(self, coro):
        task = asyncio.create_task(coro)
        self.tasks.append(task)
        logger.debug(f"Task added: {
            task.get_name() if hasattr(task, 'get_name') 
            else task}")
        return task

    async def cancel_all(self):
        logger.info("Cancelling all tasks...")
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()
        logger.info("All tasks cancelled.")