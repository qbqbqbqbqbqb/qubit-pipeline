from abc import ABC, abstractmethod
from src.utils.log_utils import get_logger


class EventProcessor(ABC):


    SUBSCRIPTIONS = {}

    def __init__(self, name: str):
        self.name = name
        self.logger = get_logger(name)
        self.event_bus = None

    def register_subscriptions(self, event_bus) -> None:
        self.event_bus = event_bus

        if not self.event_bus:
            self.logger.warning("[%s] No event_bus provided", self.name)
            return

        for event_type, handler_name in self.SUBSCRIPTIONS.items():
            handler = getattr(self, handler_name, None)
            if handler and callable(handler):
                self.event_bus.subscribe(event_type, handler)
                self.logger.info(f"[{self.name}] Registered subscription: {event_type}")
            else:
                self.logger.warning(f"[{self.name}] Handler '{handler_name}' not found for '{event_type}'")

    @abstractmethod
    async def handle_event(self, event):
        pass
