"""
<summary>
Base class for components that subscribe to and handle events from the event bus.
</summary>
"""

from abc import ABC, abstractmethod
from src.qubit.utils.log_utils import get_logger


class EventProcessor(ABC):
    """
    <summary>
    Abstract base for stateless event consumers. Subclasses declare SUBSCRIPTIONS
    mapping event type strings to handler method names, and implement handle_event.
    </summary>
    """

    SUBSCRIPTIONS = {}

    def __init__(self, name: str):
        """
        <summary>Create a named processor with its own logger.</summary>
        <param name="name">Human-readable name used in log output.</param>
        """
        self.name = name
        self.logger = get_logger(name)
        self.event_bus = None

    def register_subscriptions(self, event_bus) -> None:
        """
        <summary>Bind the event types declared in SUBSCRIPTIONS to local handler methods on the bus.</summary>
        <param name="event_bus">The EventBus instance to subscribe against.</param>
        """
        if not event_bus:
            self.logger.warning("[%s] No event_bus provided — subscriptions not registered", self.name)
            return
        self.event_bus = event_bus

        for event_type, handler_name in self.SUBSCRIPTIONS.items():
            handler = getattr(self, handler_name, None)
            if handler and callable(handler):
                self.event_bus.subscribe(event_type, handler)
                self.logger.info("[%s] Registered subscription: %s", self.name, event_type)
            else:
                self.logger.warning("[%s] Handler '%s' not found for '%s'", self.name, handler_name, event_type)

    @abstractmethod
    async def handle_event(self, event):
        """
        <summary>Process an incoming event.</summary>
        <param name="event">The Event instance to handle.</param>
        """
        pass
