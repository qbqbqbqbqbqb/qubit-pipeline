"""
Core EventProcessor base class — for pure, stateless event reactors.

Use this base class for any component whose only job is to react to events
without owning its own execution loop or long-lived resources.

Typical use cases:
- Input Processing layer (ConversationProcessor, ModerationProcessor, etc.)
- MemoryWriter (pure writes from events)
- Any thin adapter that normalises or filters events

Key contract:
- No _run() method
- No ownership of queues or background tasks
- All work happens synchronously inside handle_event() (or async if needed)
- Subscriptions are declared in the SUBSCRIPTIONS class attribute

If your component needs to own a loop, a queue, or background work, inherit from Service instead.
"""

from abc import ABC, abstractmethod
from src.utils.log_utils import get_logger


class EventProcessor(ABC):
    """
    Base class for pure event reactors.

    An EventProcessor is the correct abstraction when a component's only
    responsibility is to transform or react to events in a deterministic way.

    Characteristics:
    - Stateless or minimally stateful (state should be external when possible)
    - No ownership of execution loops
    - Work is triggered exclusively via the EventBus
    - Fast, predictable, and easy to test in isolation

    Subclasses must implement handle_event().
    Subscriptions are declared on the class via the SUBSCRIPTIONS dict.
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
