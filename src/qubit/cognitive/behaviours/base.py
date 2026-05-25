from abc import ABC, abstractmethod
from datetime import datetime, timezone


class Behavior(ABC):
    """
    Abstract base for a single decision strategy in the cognitive layer.

    Each concrete behavior implements one possible action the bot can take
    (e.g. respond to chat, emit monologue, react to frontend command).

    Contract:
    - Receives a context dict from DecisionEngine._build_context()
    - Returns a decision dict (with 'type' key) if it wants to act, else None
    - Must be completely stateless; all state lives in the context or the tracker
    - The first behavior in the list that returns a decision wins the cycle

    This design makes it trivial to add, remove, or reorder behaviours without
    touching the decision engine.
    """

    def __init__(self, name: str):
        self.name = name
        self.enabled = True
        self.last_triggered = datetime.now(timezone.utc)

    @abstractmethod
    async def tick(self, context: dict) -> dict | None:
        """
        Evaluate the current context and decide whether to trigger this behavior.

        Args:
            context: Snapshot from ActivityTracker + feature flags + timers.

        Returns:
            A decision dict (e.g. {"type": "response", "prompt": ...}) or None.
            Only the first non-None decision in the ordered list is executed.
        """
        pass
