from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List

class InputPriorityQueue:
    """
    Bounded priority queue for pending user inputs in the cognitive layer.

    Owned exclusively by ActivityTracker. Stores recent messages with pre-computed
    base priorities and full event objects for later use by DecisionEngine and behaviours.

    Scoring combines:
    - Source weight (STT inputs get 10x priority over chat)
    - Quality heuristics (longer messages, questions, direct mentions)
    - Recency decay (older messages lose priority over time)

    The queue is bounded (default maxlen=12) to prevent unbounded memory growth.
    get_best() applies recency on the fly without modifying stored data.
    """

    def __init__(self, maxlen: int = 12):
        self.messages: deque[Dict[str, Any]] = deque(maxlen=maxlen)

    def add(self, text: str, source: str, event: Any) -> None:
        """
        Add a new input message to the queue with computed priority metadata.

        Stores the raw event for later use by behaviours (e.g. to extract user info).
        Priority is calculated once at insert time for efficiency.
        """
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
        """
        Return the single highest-priority pending message after applying recency decay.

        Recency is computed at read time so that waiting messages gradually lose priority.
        Does not remove the message; caller must call remove() after use.
        Returns None if the queue is empty.
        """
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
        """
        Remove a specific message (typically after it has been selected and processed).
        Safe no-op if the message is no longer present (e.g. due to queue eviction).
        """
        if message in self.messages:
            self.messages.remove(message)

    def _calculate_quality(self, text: str) -> float:
        """Heuristic quality score based on message characteristics (0.0 - 2.5 range)."""
        length = min(len(text) / 100.0, 1.0)
        question = 1.0 if "?" in text else 0.0
        mention = 0.5 if "@" in text else 0.0
        return length + question + mention

    def _get_source_priority(self, source: str) -> float:
        """
        Base multiplier by input source.
        STT gets highest weight because voice input is considered higher intent.
        """
        return {
            "user_input_stt": 10.0,
            "user_input_chat_message": 2.0,
        }.get(source, 1.0)