from abc import ABC, abstractmethod
from datetime import datetime, timezone
from dataclasses import dataclass

@dataclass
class BehaviorContext:
    activity_score: float
    pending_messages: list
    features: dict
    last_autonomous_speech_time: datetime
    last_user_input_response_time: datetime

class Behavior(ABC):
    def __init__(self, name: str):
        self.name = name
        self.enabled = True
        self.last_triggered = datetime.now(timezone.utc)

    @abstractmethod
    async def tick(self, context: BehaviorContext) -> dict | None:
        """Return event dict to publish, or None."""
        pass