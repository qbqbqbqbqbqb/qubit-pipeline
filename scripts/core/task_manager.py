import asyncio

from scripts.utils.log_utils import get_logger
logger = get_logger("TaskManager")

class TaskManager:
    def __init__(self):
        self.tasks = []

    def add_task(self, coro):
        task = asyncio.create_task(coro)
        self.tasks.append(task)
        return task

    async def cancel_all(self):
        logger.info("Cancelling all tasks...")
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()
        logger.info("All tasks cancelled.")