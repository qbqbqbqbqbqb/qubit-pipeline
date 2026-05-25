"""
Core EventProcessor base class (pure event reactors).

CONTRACT (see ARCHITECTURE.md):
- Use EventProcessor for components that ONLY react to events.
- No _run loop, no long-lived state machines, no queues they own.
- Typical examples: moderation, deduplication, normalisation, memory writes (the "writer" part),
  thin adapters that normalise external events.

This is the preferred base for the Input Processing and MemoryWriter layers.

If your component needs its own background loop or owns a queue → subclass Service instead.
"""

from abc import ABC, abstractmethod
from src.utils.log_utils import get_logger


class EventProcessor(ABC):
    """
    Lightweight base for pure event-driven reactors.

    Responsibilities:
    - Subscribe to one or more event types via SUBSCRIPTIONS
    - Perform filtering, transformation, or side-effects (e.g. write to memory)
    - Never own a main loop or long-running work

    All domain transformation logic that does not require independent execution
    should live in subclasses of this class.
    """

    SUBSCRIPTIONS = {}

    def __init__(self, name: str):
        self.name = name
        self.logger = get_logger(name)
        self.event_bus = None

    def register_subscriptions(self, event_bus) -> None:
        """Register subscriptions. Accepts the event_bus directly."""
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
        """Must be implemented by all processors."""
        pass
