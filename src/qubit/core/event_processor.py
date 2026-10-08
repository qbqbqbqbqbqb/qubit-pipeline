"""Base event processor that wires handler methods to event bus subscriptions."""

from abc import ABC, abstractmethod
from src.qubit.utils.log_utils import get_logger


class EventProcessor(ABC):
    """Abstract base for components that consume events from the event bus."""

    SUBSCRIPTIONS = {}

    def __init__(self, name: str):
        """Create a named processor with its own logger."""
        self.name = name
        self.logger = get_logger(name)
        self.event_bus = None

    def register_subscriptions(self, event_bus) -> None:
        """Bind configured event types to local handler methods on the bus."""
        self.event_bus = event_bus

        if not self.event_bus:
            self.logger.warning("[%s] No event_bus provided", self.name)
            return

        for event_type, handler_name in self.SUBSCRIPTIONS.items():
            handler = getattr(self, handler_name, None)
            if handler and callable(handler):
                self.event_bus.subscribe(event_type, handler)
                self.logger.info("[%s] Registered subscription: %s", self.name, event_type)
            else:
                self.logger.warning("[%s] Handler '%s' not found for '%s'", self.name, handler_name, event_type)

    @abstractmethod
    async def handle_event(self, event):
        """Process an incoming event."""
        pass
