from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List

class InputPriorityQueue:
    """
    Dedicated priority queue for pending chat/STT messages.

    Handles:
    - Adding messages with source-based priority
    - Quality scoring (length, question marks, mentions)
    - Recency weighting
    - Safe removal of used messages
    """

    def __init__(self, maxlen: int = 12):
        self.messages: deque[Dict[str, Any]] = deque(maxlen=maxlen)

    def add(self, text: str, source: str, event: Any) -> None:
        """Add a message with full priority calculation."""
        quality = self._calculate_quality(text)
        base_priority = self._get_source_priority(source) * quality

        self.messages.append({
            "text": text,
            "source": source,
            "timestamp": datetime.now(timezone.utc),
            "base_priority": base_priority,
            "quality": quality,
            "event": event
        })

    def get_best(self) -> Dict[str, Any] | None:
        """Return the highest-priority message (with recency applied)."""
        if not self.messages:
            return None

        now = datetime.now(timezone.utc)
        candidates = []

        for msg in self.messages:
            age_min = (now - msg["timestamp"]).total_seconds() / 60
            recency = max(0.1, 1.0 / (1 + age_min))
            full_priority = msg["base_priority"] * recency
            candidates.append((full_priority, msg))

        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    def remove(self, message: Dict[str, Any]) -> None:
        """Safely remove a message after it has been used."""
        if message in self.messages:
            self.messages.remove(message)

    def _calculate_quality(self, text: str) -> float:
        """Simple quality metrics (easy to extend with relevance later)."""
        length = min(len(text) / 100.0, 1.0)
        question = 1.0 if "?" in text else 0.0
        mention = 0.5 if "@" in text else 0.0
        return length + question + mention

    def _get_source_priority(self, source: str) -> float:
        """STT = 10×, chat = 2×, everything else = 1×."""
        return {
            "user_input_stt": 10.0,
            "user_input_chat_message": 2.0,
        }.get(source, 1.0)