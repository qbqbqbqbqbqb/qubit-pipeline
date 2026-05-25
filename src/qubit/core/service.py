"""
Core Service base class.

This is the foundational building block for any component that owns a long-running
loop, manages connections, owns a queue, or performs background work.

CONTRACT:
- Subclass Service when your component needs independent lifecycle management
  (e.g. GenerationCoordinator, OutputCoordinator, MemoryService, listeners).
- Services are started after the frontend "start" signal and stopped on shutdown.
- They automatically register event subscriptions defined in SUBSCRIPTIONS.
- They receive a dedicated _run() coroutine that runs until shutdown.

Do NOT use Service for pure event reactors (use EventProcessor instead).
Domain decision logic belongs in the Cognitive layer, not here.
"""

import asyncio
from src.utils.log_utils import get_logger


class Service:
    """
    Abstract base for long-lived components that require their own execution context.

    A Service is the correct base class when a component needs to:
    - Run an independent background loop (_run)
    - Own and drain a queue
    - Manage external connections (Twitch, WebSocket, audio, etc.)
    - Perform periodic background work (reflections, token refresh, etc.)

    Key lifecycle:
    1. start(app) is called by the runtime
    2. Subscriptions from SUBSCRIPTIONS are automatically registered
    3. The component waits for the global "start" signal
    4. _run() is launched as a background task
    5. stop() cancels the task on shutdown

    Attributes:
        name: Human-readable identifier used for logging.
        app: Reference to the central App container.
        event_bus: The global EventBus (injected on start).
        logger: Dedicated logger for this service.

    Subclasses must define SUBSCRIPTIONS when they want to react to events.
    """

    SUBSCRIPTIONS = {}

    def __init__(self, name):
        self.name = name
        self.app = None
        self.event_bus = None
        self.logger = get_logger(name)
        self._worker_task = None

    async def start(self, app):
        """
        Initialize the service and begin its lifecycle.

        This method:
        - Stores references to the App and EventBus
        - Registers all event handlers declared in SUBSCRIPTIONS
        - Waits for the global frontend "start" signal
        - Launches the background _run() task

        Should only be called by the central runtime (bootstrap / Runtime).
        """
        self.app = app
        self.event_bus = app.event_bus

        self.logger.info("[start] Starting %s — waiting for START command", self.name)

        self._register_subscriptions()

        await self._wait_for_start()

        self.logger.info("[start] %s started on frontend click", self.name)

        self.logger.info("[_register_subscriptions] %s has registered subscriptions: %s", self.name, list(self.SUBSCRIPTIONS.keys()))

        self._worker_task = asyncio.create_task(self._run())

    async def _wait_for_start(self):
        await self.app.state.start.wait()

    async def _run(self):
        self.logger.info("[_run] %s main loop is running", self.name)

    async def stop(self):
        self.logger.info("[stop] Stopping %s", self.name)
        if self._worker_task:
            self._worker_task.cancel()
            await asyncio.gather(self._worker_task, return_exceptions=True)

    def _register_subscriptions(self):
        for event_type, handler_name in self.SUBSCRIPTIONS.items():
            handler = getattr(self, handler_name)
            if handler:
                self.event_bus.subscribe(event_type, handler)
                self.logger.info(f"[{self.name}] Registered subscription: {event_type}")
            else:
                self.logger.warning(f"[{self.name}] Handler {handler_name} not found")
