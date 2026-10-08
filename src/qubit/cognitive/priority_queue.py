"""
InputPriorityQueue - priority queue for pending user inputs in the cognitive layer.

Owned exclusively by ActivityTracker. STT and chat are stored in separate
lists so chat volume can never evict a live STT message (fixed-size reserved
slots), and every message has a hard TTL so a high-priority-but-stale message
can't win a decision cycle long after the moment it was relevant has passed.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4


class InputPriorityQueue:
    DEFAULT_MAXLEN = 12
    DEFAULT_STT_SLOTS = 2
    DEFAULT_MAX_AGE_SECONDS = 90.0

    RECENCY_FLOOR = 0.1

    SOURCE_PRIORITIES = {
        "user_input_stt": 10.0,
        "user_input_chat_message": 2.0,
    }
    DEFAULT_SOURCE_PRIORITY = 1.0

    # Chat-only quality heuristic constants. STT is scored at a fixed max
    # quality instead — see _score_new_message().
    QUALITY_LENGTH_NORMALIZER = 100.0
    QUALITY_QUESTION_BONUS = 1.0
    QUALITY_MENTION_BONUS = 0.5
    # Applied when a message contains @someone who is NOT in the whitelist —
    # i.e. a viewer-to-viewer conversation that isn't directed at Qubit.
    # Set low enough that the message is near-invisible at high activity.
    QUALITY_OFFMENTION_PENALTY = 0.85
    STT_QUALITY = 1.0

    STT_SOURCE = "user_input_stt"
    AT_SIGN = "@"

    def __init__(
        self,
        maxlen: int = DEFAULT_MAXLEN,
        stt_slots: int = DEFAULT_STT_SLOTS,
        max_age_seconds: float = DEFAULT_MAX_AGE_SECONDS,
        mention_whitelist: frozenset[str] | None = None,
    ):
        self.chat_maxlen = maxlen
        self.stt_slots = max(1, stt_slots)  # guard against a 0/negative config silently disabling STT storage
        self.max_age_seconds = max_age_seconds
        # Lowercased names that are allowed to carry the mention bonus.
        # Any @name not in this set triggers the off-mention penalty instead.
        # An empty/None whitelist disables the penalty entirely (safe default
        # for tests and environments where settings aren't wired up yet).
        self.mention_whitelist: frozenset[str] = mention_whitelist or frozenset()
        self.chat_messages: List[Dict[str, Any]] = []
        self.stt_messages: List[Dict[str, Any]] = []

    def add(self, text: str, source: str, event: Any) -> None:
        quality, base_priority = self._score_new_message(text, source)
        msg = {
            "text": text,
            "source": source,
            "timestamp": datetime.now(timezone.utc),
            "base_priority": base_priority,
            "quality": quality,
            "event": event,
        }

        msg["_id"] = str(uuid4())

        if source == self.STT_SOURCE:
            self._append_bounded(self.stt_messages, msg, self.stt_slots)
        else:
            self._append_bounded(self.chat_messages, msg, self.chat_maxlen)

    def get_best(self) -> Optional[Dict[str, Any]]:
        """
        Return the single highest-priority, non-expired pending message after
        applying recency decay. Does not remove it; caller must call remove().
        """
        now = datetime.now(timezone.utc)
        candidates = [
            (self._score_for_ranking(msg, now), msg)
            for msg in (*self.stt_messages, *self.chat_messages)
            if not self._is_expired(msg, now)
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda pair: pair[0], reverse=True)
        return candidates[0][1]

    def remove(self, message: Dict[str, Any]) -> None:
        """Remove a specific message by its assigned id. Safe no-op if it's no longer present."""
        msg_id = message.get("_id")
        if not msg_id:
            return
        for bucket in (self.stt_messages, self.chat_messages):
            for i, m in enumerate(bucket):
                if m.get("_id") == msg_id:
                    del bucket[i]
                    return

    def has_source(self, source: str) -> bool:
        """Return True if the queue currently contains any message from the given source."""
        if source == self.STT_SOURCE:
            return bool(self.stt_messages)
        return any(m.get("source") == source for m in self.chat_messages)

    @property
    def messages(self) -> List[Dict[str, Any]]:
        """Flat view — keeps DecisionEngine's len(queue.messages) logging line working unchanged."""
        return [*self.stt_messages, *self.chat_messages]

    def _append_bounded(self, bucket: List[Dict[str, Any]], msg: Dict[str, Any], limit: int) -> None:
        bucket.append(msg)
        if len(bucket) > limit:
            bucket.pop(0)

    def _score_new_message(self, text: str, source: str) -> tuple[float, float]:
        if source == self.STT_SOURCE:
            # Spoken input isn't scored by the chat-shaped quality heuristic
            # (length/question/@-mention) — treated as max quality outright.
            return self.STT_QUALITY, self._source_priority(source)
        quality = self._calculate_quality(text)
        return quality, self._source_priority(source) * quality

    def _is_expired(self, msg: Dict[str, Any], now: datetime) -> bool:
        age_sec = (now - msg["timestamp"]).total_seconds()
        return age_sec > self.max_age_seconds

    def _score_for_ranking(self, msg: Dict[str, Any], now: datetime) -> float:
        age_min = (now - msg["timestamp"]).total_seconds() / 60
        recency = max(self.RECENCY_FLOOR, 1.0 / (1 + age_min))
        return msg["base_priority"] * recency

    def _calculate_quality(self, text: str) -> float:
        """Heuristic quality score based on message characteristics (0.0 - 2.5 range). Chat only."""
        length = min(len(text) / self.QUALITY_LENGTH_NORMALIZER, 1.0)
        question = self.QUALITY_QUESTION_BONUS if "?" in text else 0.0
        mention, penalty = self._score_mentions(text)
        return max(0.0, length + question + mention - penalty)

    def _score_mentions(self, text: str) -> tuple[float, float]:
        """
        Return (bonus, penalty) for @ mentions in the message.

        Rules:
        - No @ in text              -> (0.0, 0.0)
        - @ targeting a whitelisted name (case-insensitive) -> (MENTION_BONUS, 0.0)
        - @ targeting an off-whitelist name                 -> (0.0, OFFMENTION_PENALTY)
        - Whitelist is empty (unconfigured)                 -> treat @ as neutral (0.0, 0.0)

        If a message mentions both a whitelisted and a non-whitelisted name
        (e.g. "@qubit and @someguy"), the whitelisted mention wins — the
        message is at least partially directed at us.
        """
        if self.AT_SIGN not in text:
            return 0.0, 0.0

        if not self.mention_whitelist:
            # Whitelist not configured — don't penalise anything.
            return 0.0, 0.0

        # Extract the name token immediately following each @.
        # Strip trailing punctuation so "@qubit," and "@qubit." both resolve.
        mentioned = {
            word[1:].rstrip(",.!?:;").lower()
            for word in text.split()
            if word.startswith(self.AT_SIGN) and len(word) > 1
        }

        if not mentioned:
            return 0.0, 0.0

        if mentioned & self.mention_whitelist:
            # At least one mention is directed at us.
            return self.QUALITY_MENTION_BONUS, 0.0

        # Every @ is directed at someone else.
        return 0.0, self.QUALITY_OFFMENTION_PENALTY

    def _source_priority(self, source: str) -> float:
        """Base multiplier by input source. STT gets highest weight — voice input is higher intent."""
        return self.SOURCE_PRIORITIES.get(source, self.DEFAULT_SOURCE_PRIORITY)