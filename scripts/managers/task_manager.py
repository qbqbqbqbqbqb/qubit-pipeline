import asyncio
from scripts.utils.log_utils import get_logger


class TaskManager:
    """
    Manages async task lifecycle for the VTuber bot.

    Provides centralised task creation, tracking, and cancellation
    to ensure clean shutdown of all background operations.
    """

    def __init__(self):
        self.logger = get_logger("TaskManager")
        self.tasks = []
        
    def add_task(self, coro):
        task = asyncio.create_task(coro)
        self.tasks.append(task)
        self.logger.debug(f"[add_task] Task added: {task.get_name() if hasattr(task, 'get_name') else task}")
        return task

    async def cancel_all(self):
        self.logger.info("[cancel_all] Cancelling all tasks...")
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()
        self.logger.info("[cancel_all] All tasks cancelled.")