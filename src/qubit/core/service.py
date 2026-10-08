"""Base service class with lifecycle management and event bus integration."""

import asyncio
from src.qubit.utils.log_utils import get_logger


class Service:
    """
    Long-lived background service managed by the application runtime.

    Lifecycle:
        bootstrap  -> __init__()          construct, no I/O
        run_app    -> attach(app)         bind to app and event bus, register subscriptions
        run_app    -> wait_for_start()    block until frontend sends start command (optional)
        run_app    -> launch()            spawn _run() as a background task
        run_app    -> stop()              cancel the task on shutdown

    Separating attach/wait/launch from a single monolithic start() means:
    - Services that must run before the start signal (e.g. WebSocketServer)
      do not need to override the entire lifecycle.
    - Testing a service in isolation does not require faking a start event.
    - run_app controls the startup sequence, not each service individually.
    """

    SUBSCRIPTIONS: dict = {}
    WAIT_FOR_START: bool = True

    def __init__(self, name: str) -> None:
        self.name = name
        self.app = None
        self.event_bus = None
        self.logger = get_logger(name)
        self._worker_task: asyncio.Task | None = None

    def attach(self, app) -> None:
        """Bind to the app and register event subscriptions."""
        self.app = app
        self.event_bus = app.event_bus
        self._register_subscriptions()
        if self.SUBSCRIPTIONS:
            self.logger.info(
                "[attach] %s registered subscriptions: %s",
                self.name, list(self.SUBSCRIPTIONS.keys()),
            )

    def launch(self) -> None:
        """Spawn the background worker task. Call after attach() and any required wait."""
        self._worker_task = asyncio.create_task(self._run())
        self.logger.info("[launch] %s worker task started", self.name)

    async def _run(self) -> None:
        """Main worker loop — override in subclasses."""

    async def stop(self) -> None:
        """Cancel the worker task and wait for it to finish."""
        self.logger.info("[stop] Stopping %s", self.name)
        if self._worker_task:
            self._worker_task.cancel()
            await asyncio.gather(self._worker_task, return_exceptions=True)

    def _register_subscriptions(self) -> None:
        """Bind event types to handler methods declared in SUBSCRIPTIONS."""
        for event_type, handler_name in self.SUBSCRIPTIONS.items():
            handler = getattr(self, handler_name, None)
            if handler is not None:
                self.event_bus.subscribe(event_type, handler)
            else:
                self.logger.warning(
                    "[_register_subscriptions] %s: handler '%s' not found for event '%s'",
                    self.name, handler_name, event_type,
                )
