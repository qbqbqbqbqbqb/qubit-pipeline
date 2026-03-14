
from src.utils.log_utils import get_logger

logger = get_logger(__name__)

class Service:

    SUBSCRIPTIONS = {}

    def __init__(self, name):
        self.name = name
        self.event_bus = None

    async def start(self, app):
        self.app = app
        self.event_bus = app.event_bus
        logger.info(f"Starting {self.name} — waiting for START command")

        await self.app.state.start.wait() 
        if self.app.state.start.is_set():
            logger.info(f"{self.name} started on frontend click")

        self._register_subscriptions()


    async def stop(self):
        pass

    def _register_subscriptions(self):
        for event_type, handler_name in self.SUBSCRIPTIONS.items():
            handler = getattr(self, handler_name)
            self.event_bus.subscribe(event_type, handler)