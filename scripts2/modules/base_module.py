import asyncio
from scripts2.utils.log_utils import get_logger
"""
Base module for all modules in the scripts2 system.

This module provides a BaseModule class that serves as the foundation for all
specialized modules within the application. It handles common functionality such
    """
    Base class for all modules in the scripts2 application.

    This class provides a template for implementing asynchronous modules that can be
    started, run in a loop, and stopped gracefully. It manages logging, task creation,
    and cancellation to ensure clean shutdowns.

    Subclasses should override the `run` method to implement their specific logic.

    Attributes:
        name (str): The name of the module, used for logging and task naming.
        logger (Logger): Logger instance for this module.
        _running (bool): Flag indicating if the module is currently running.
        _task (asyncio.Task): The asynchronous task running the module's main loop.
    """
as initialization with logging, asynchronous task management, and graceful shutdown.

Classes:
    BaseModule: Abstract base class for implementing application modules.
"""



class BaseModule:
    def __init__(self, name):
        """
        Initialize the BaseModule with a given name.

        Sets up the module's name, logger, running state, and task placeholder.
        The logger is created using the provided name for consistent logging.

        Args:
            name (str): The unique name for this module instance, used for logging
                and task identification.
        """
        self.name = name
        self.logger = get_logger(name)
        self._running = False
        self._task = None

    async def start(self):
        """
        Start the module and begin its asynchronous execution.

        This method sets the running flag to True, creates an asynchronous task
        for the `run` method, and waits for it to complete. The task is named
        using the module's name for easier debugging.

        This method will run indefinitely until the module is stopped externally.

        Raises:
            Any exceptions raised by the `run` method or task cancellation.
        """
        self.logger.info(f"{self.name} starting...")
        self._running = True
        self._task = asyncio.create_task(self.run(), name=f"{self.name}-task")
        await self._task
        
    async def run(self):
        """
        Main execution loop for the module.

        This method should be overridden in subclasses to implement the specific
        functionality of the module. The base implementation simply logs that
        the module is running and does nothing else.

        By default, this method runs once and completes. Subclasses can implement
        loops or periodic tasks here, checking `self._running` to determine when
        to stop.

        Example:
            In a subclass: while self._running: await asyncio.sleep(1)
        """
        self.logger.info(f"[run] Running {self.name}")

    async def stop(self):
        """
        Stop the module and perform cleanup.

        This method sets the running flag to False, cancels the running task,
        and waits for it to finish. It handles the CancelledError gracefully
        and logs the cancellation.

        After calling this method, the module should not be restarted without
        proper reinitialization.

        Note:
            This method is asynchronous and should be awaited to ensure
            proper cleanup.
        """
        self.logger.info(f"{self.name} stopping...")
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                self.logger.info(f"{self.name} task cancelled.")