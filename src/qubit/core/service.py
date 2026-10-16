"""
<summary>
Base service class providing lifecycle management and event bus integration
for all long-lived background components.
</summary>
"""

import asyncio
from src.qubit.utils.log_utils import get_logger


class Service:
    """
    <summary>
    Long-lived background service managed by the application runtime.
    </summary>
    <remarks>
    Lifecycle:
        bootstrap  -> __init__()       construct, no I/O
        run_app    -> attach(app)      bind to app and event bus, register subscriptions
        run_app    -> launch()         spawn _run() as a background task
        run_app    -> stop()           cancel the task on shutdown

    Separating attach and launch means services that must run before the
    start signal (e.g. WebSocketServer) do not need to override the entire
    lifecycle, and run_app controls the startup sequence rather than each
    individual service.
    </remarks>
    """

    SUBSCRIPTIONS: dict = {}
    WAIT_FOR_START: bool = True

    def __init__(self, name: str) -> None:
        """
        <summary>Initialise the service with a name and a logger.</summary>
        <param name="name">Human-readable service name used in log output.</param>
        """
        self.name = name
        self.app = None
        self.event_bus = None
        self.logger = get_logger(name)
        self._worker_task: asyncio.Task | None = None

    def attach(self, app) -> None:
        """
        <summary>Bind to the app and register event subscriptions.</summary>
        <param name="app">The root App instance.</param>
        """
        self.app = app
        self.event_bus = app.event_bus
        self._register_subscriptions()
        if self.SUBSCRIPTIONS:
            self.logger.info(
                "[attach] %s registered subscriptions: %s",
                self.name, list(self.SUBSCRIPTIONS.keys()),
            )

    def launch(self) -> None:
        """
        <summary>Spawn the background worker task. Call after attach().</summary>
        """
        self._worker_task = asyncio.create_task(self._run())
        self.logger.info("[launch] %s worker task started", self.name)

    async def _run(self) -> None:
        """
        <summary>Main worker loop. Override in subclasses to implement service logic.</summary>
        """

    async def stop(self) -> None:
        """
        <summary>Cancel the worker task and wait for it to finish.</summary>
        """
        self.logger.info("[stop] Stopping %s", self.name)
        if self._worker_task:
            self._worker_task.cancel()
            await asyncio.gather(self._worker_task, return_exceptions=True)

    def _register_subscriptions(self) -> None:
        """
        <summary>Bind event types to handler methods declared in SUBSCRIPTIONS.</summary>
        """
        for event_type, handler_name in self.SUBSCRIPTIONS.items():
            handler = getattr(self, handler_name, None)
            if handler is not None:
                self.event_bus.subscribe(event_type, handler)
            else:
                self.logger.warning(
                    "[_register_subscriptions] %s: handler '%s' not found for event '%s'",
                    self.name, handler_name, event_type,
                )
