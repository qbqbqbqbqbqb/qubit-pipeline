from abc import ABC, abstractmethod
from datetime import datetime, timezone


class Behavior(ABC):
    """
    Pure strategy for one possible decision the system can make.

    A behavior receives a plain dict context (built by DecisionEngine)
    and returns either a decision dict or None.

    Behaviours must be stateless with respect to the rest of the system.
    They never reach outside the context they are given.
    """

    def __init__(self, name: str):
        self.name = name
        self.enabled = True
        self.last_triggered = datetime.now(timezone.utc)

    @abstractmethod
    async def tick(self, context: dict) -> dict | None:
        """Return a decision dict to execute, or None if this behavior does not trigger."""
        pass
