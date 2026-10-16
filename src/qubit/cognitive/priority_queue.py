"""
<summary>
InputPriorityQueue — priority queue for pending user inputs in the cognitive layer.
Owned exclusively by ActivityTracker.
</summary>
<remarks>
STT and chat messages are stored in separate lists so chat volume can never evict
a live STT message (fixed-size reserved slots). Every message carries a hard TTL
so a high-priority-but-stale entry cannot win a decision cycle after its moment
has passed.
</remarks>
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4


class InputPriorityQueue:
    """
    <summary>
    Dual-bucket priority queue that keeps STT and chat messages separate to
    guarantee STT reservation slots regardless of chat volume.
    </summary>
    """

    DEFAULT_MAXLEN = 12
    DEFAULT_STT_SLOTS = 2
    DEFAULT_MAX_AGE_SECONDS = 90.0

    RECENCY_FLOOR = 0.1

    SOURCE_PRIORITIES = {
        "user_input_stt": 10.0,
        "user_input_chat_message": 2.0,
    }
    DEFAULT_SOURCE_PRIORITY = 1.0

    # Chat-only quality heuristic constants. STT is scored at a fixed max quality.
    QUALITY_LENGTH_NORMALIZER = 100.0
    QUALITY_QUESTION_BONUS = 1.0
    QUALITY_MENTION_BONUS = 0.5
    # Applied when a message contains @someone not in the whitelist —
    # a viewer-to-viewer conversation not directed at Qubit.
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
        """
        <summary>Initialise the queue with capacity and mention whitelist settings.</summary>
        <param name="maxlen">Maximum number of chat messages to retain.</param>
        <param name="stt_slots">Number of reserved slots for STT messages.</param>
        <param name="max_age_seconds">Maximum age in seconds before a message expires.</param>
        <param name="mention_whitelist">
        Lowercased names that earn the mention bonus. Names outside this set
        trigger the off-mention penalty instead. An empty or None whitelist
        disables the penalty entirely.
        </param>
        """
        self.chat_maxlen = maxlen
        self.stt_slots = max(1, stt_slots)
        self.max_age_seconds = max_age_seconds
        self.mention_whitelist: frozenset[str] = mention_whitelist or frozenset()
        self.chat_messages: List[Dict[str, Any]] = []
        self.stt_messages: List[Dict[str, Any]] = []

    def add(self, text: str, source: str, event: Any) -> None:
        """
        <summary>Score and enqueue a new message into the appropriate bucket.</summary>
        <param name="text">The message text.</param>
        <param name="source">The canonical source string (e.g. 'user_input_stt').</param>
        <param name="event">The originating Event object, stored for later retrieval.</param>
        """
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
        <summary>
        Return the single highest-priority, non-expired pending message after
        applying recency decay. Does not remove it; caller must call remove().
        </summary>
        <returns>The best message dict, or None if no eligible messages exist.</returns>
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
        """
        <summary>Remove a specific message by its assigned id. Safe no-op if no longer present.</summary>
        <param name="message">The message dict to remove (must contain '_id').</param>
        """
        msg_id = message.get("_id")
        if not msg_id:
            return
        for bucket in (self.stt_messages, self.chat_messages):
            for i, m in enumerate(bucket):
                if m.get("_id") == msg_id:
                    del bucket[i]
                    return

    def has_source(self, source: str) -> bool:
        """
        <summary>Return True if the queue currently contains any message from the given source.</summary>
        <param name="source">The canonical source string to check.</param>
        <returns>True if at least one message from this source is queued.</returns>
        """
        if source == self.STT_SOURCE:
            return bool(self.stt_messages)
        return any(m.get("source") == source for m in self.chat_messages)

    @property
    def messages(self) -> List[Dict[str, Any]]:
        """
        <summary>Flat view of all queued messages across both buckets.</summary>
        """
        return [*self.stt_messages, *self.chat_messages]

    def _append_bounded(self, bucket: List[Dict[str, Any]], msg: Dict[str, Any], limit: int) -> None:
        bucket.append(msg)
        if len(bucket) > limit:
            bucket.pop(0)

    def _score_new_message(self, text: str, source: str) -> tuple[float, float]:
        if source == self.STT_SOURCE:
            # Spoken input is treated as max quality — not subject to the
            # chat-shaped length/question/@-mention heuristic.
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
        """
        <summary>Heuristic quality score based on message characteristics (0.0–2.5 range). Chat only.</summary>
        <param name="text">The chat message text to score.</param>
        <returns>A float quality score.</returns>
        """
        length = min(len(text) / self.QUALITY_LENGTH_NORMALIZER, 1.0)
        question = self.QUALITY_QUESTION_BONUS if "?" in text else 0.0
        mention, penalty = self._score_mentions(text)
        return max(0.0, length + question + mention - penalty)

    def _score_mentions(self, text: str) -> tuple[float, float]:
        """
        <summary>
        Return (bonus, penalty) for @ mentions in the message.
        </summary>
        <remarks>
        Rules:
          - No @ in text                              -> (0.0, 0.0)
          - @ targeting a whitelisted name            -> (MENTION_BONUS, 0.0)
          - @ targeting an off-whitelist name         -> (0.0, OFFMENTION_PENALTY)
          - Whitelist is empty (unconfigured)         -> (0.0, 0.0) — no penalty applied

        If a message mentions both a whitelisted and a non-whitelisted name,
        the whitelisted mention wins.
        </remarks>
        <param name="text">The chat message text.</param>
        <returns>A (bonus, penalty) float tuple.</returns>
        """
        if self.AT_SIGN not in text:
            return 0.0, 0.0

        if not self.mention_whitelist:
            return 0.0, 0.0

        mentioned = {
            word[1:].rstrip(",.!?:;").lower()
            for word in text.split()
            if word.startswith(self.AT_SIGN) and len(word) > 1
        }

        if not mentioned:
            return 0.0, 0.0

        if mentioned & self.mention_whitelist:
            return self.QUALITY_MENTION_BONUS, 0.0

        return 0.0, self.QUALITY_OFFMENTION_PENALTY

    def _source_priority(self, source: str) -> float:
        """
        <summary>Base priority multiplier by input source. STT receives the highest weight.</summary>
        <param name="source">The canonical source string.</param>
        <returns>The base priority multiplier.</returns>
        """
        return self.SOURCE_PRIORITIES.get(source, self.DEFAULT_SOURCE_PRIORITY)
