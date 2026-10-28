"""
Base service class providing lifecycle management and event bus integration
for all long-lived background components.
"""

import asyncio
import math
from src.qubit.utils.log_utils import get_logger


class Service:
    """
    Long-lived background service managed by the application runtime.

    Lifecycle:
        bootstrap  -> __init__()       construct, no I/O
        run_app    -> attach(app)      bind to app and event bus, register subscriptions
        run_app    -> launch()         spawn _run() as a background task under the supervisor
        run_app    -> stop()           cancel tasks on shutdown

    _run() is wrapped in a supervisor loop. If _run() raises, the supervisor
    waits with exponential backoff and restarts it automatically, up to
    MAX_RESTARTS attempts. Set MAX_RESTARTS = 0 to disable supervision.
    """

    SUBSCRIPTIONS: dict = {}
    WAIT_FOR_START: bool = True
    MAX_RESTARTS: int = 10
    _BASE_BACKOFF: float = 2.0
    _MAX_BACKOFF: float = 60.0

    def __init__(self, name: str) -> None:
        self.name = name
        self.app = None
        self.event_bus = None
        self.logger = get_logger(name)
        self._worker_task: asyncio.Task | None = None

    def attach(self, app) -> None:
        self.app = app
        self.event_bus = app.event_bus
        self._register_subscriptions()
        if self.SUBSCRIPTIONS:
            self.logger.info(
                "[attach] %s registered subscriptions: %s",
                self.name, list(self.SUBSCRIPTIONS.keys()),
            )

    def launch(self) -> None:
        self._worker_task = asyncio.create_task(self._supervised_run())
        self.logger.info("[launch] %s worker task started", self.name)

    async def _supervised_run(self) -> None:
        """Wraps _run() with restart-on-crash and exponential backoff."""
        attempts = 0
        while not self.app.state.shutdown.is_set():
            try:
                await self._run()
                # _run() returned cleanly — service chose to exit
                return
            except asyncio.CancelledError:
                return
            except Exception as exc:
                attempts += 1
                if self.MAX_RESTARTS > 0 and attempts > self.MAX_RESTARTS:
                    self.logger.error(
                        "[_supervised_run] %s crashed %d times — giving up: %s",
                        self.name, attempts, exc,
                    )
                    self._report_health("error", str(exc))
                    return

                delay = min(self._BASE_BACKOFF * math.pow(2, attempts - 1), self._MAX_BACKOFF)
                self.logger.warning(
                    "[_supervised_run] %s crashed (attempt %d/%d): %s — restarting in %.0fs",
                    self.name, attempts,
                    self.MAX_RESTARTS if self.MAX_RESTARTS > 0 else "inf",
                    exc, delay,
                )
                self._report_health("reconnecting", str(exc))
                await asyncio.sleep(delay)

    async def _run(self) -> None:
        """Main worker loop. Override in subclasses."""

    async def stop(self) -> None:
        self.logger.info("[stop] Stopping %s", self.name)
        if self._worker_task:
            self._worker_task.cancel()
            await asyncio.gather(self._worker_task, return_exceptions=True)

    def _register_subscriptions(self) -> None:
        for event_type, handler_name in self.SUBSCRIPTIONS.items():
            handler = getattr(self, handler_name, None)
            if handler is not None:
                self.event_bus.subscribe(event_type, handler)
            else:
                self.logger.warning(
                    "[_register_subscriptions] %s: handler '%s' not found for event '%s'",
                    self.name, handler_name, event_type,
                )

    def _report_health(self, status: str, detail: str = "") -> None:
        """Update this service's entry in RuntimeState health map."""
        try:
            health = getattr(self.app.state, "health", None)
            if health is not None:
                health[self.name] = {"status": status, "detail": detail}
        except Exception:
            pass

    def _set_connected(self) -> None:
        self._report_health("connected")

    def _set_disconnected(self, reason: str = "") -> None:
        self._report_health("disconnected", reason)