from abc import ABC, abstractmethod
from datetime import datetime, timezone


class Behavior(ABC):
    """
    Abstract base for a pluggable decision strategy in the cognitive layer.

    New contract (scored proposal model):
    - Receives rich context from DecisionEngine._build_context()
    - Returns either None (no proposal) or a scored proposal dict:
        {
            "type": "response" | "monologue",
            "score": float,          # 0.0–1.0 (higher wins). STT responses may exceed 1.0
            "reason": str,
            "best_message": dict | None,   # only for "response"
            "topic": str | None,           # only for "monologue"
        }
    - Completely stateless. All timers, features, queue state come from context.
    - DecisionEngine collects proposals from ALL behaviors every cycle, then picks the single highest-scoring one.
    - This enables dynamic trade-offs (e.g. strong STT priority at every activity level + natural idle speech at low activity).

    Adding new behaviors (raids, emotes, alerts, etc.) is now trivial and safe.
    """

    def __init__(self, name: str):
        self.name = name
        self.enabled = True
        self.last_triggered = datetime.now(timezone.utc)

    @abstractmethod
    async def tick(self, context: dict) -> dict | None:
        """
        Evaluate context and return a scored proposal or None.

        The returned dict MUST contain at minimum:
            "type", "score", "reason"
        Optional keys: "best_message", "topic" depending on type.
        """
        pass
