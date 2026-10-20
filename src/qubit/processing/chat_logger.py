"""
<summary>
ChatLogger — appends filtered chat messages to a JSONL file for training data collection.
</summary>
<remarks>
LAYER: Input Processing

Subscribes to the *_filtered event variants produced by ConversationProcessor so only
deduplicated, non-stale messages are logged. Logging is gated behind the chat_logging
FeatureFlag; when the flag is off this processor is a no-op with no I/O.

Output file: logs/chat_training.jsonl  (one JSON object per line)
Schema per line:
    {
        "timestamp": "<ISO-8601 UTC>",
        "source":    "twitch" | "kick" | "stt",
        "user":      "<username or 'streamer'>",
        "text":      "<message text>"
    }

The file is opened in append mode on each write so the process can restart without
losing previously collected data.
</remarks>
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from src.qubit.core.event_processor import EventProcessor


_LOG_PATH = Path("logs/chat_training.jsonl")

_SOURCE_MAP = {
    "twitch_chat_filtered": "twitch",
    "kick_chat_filtered":   "kick",
    "stt_filtered":         "stt",
}


class ChatLogger(EventProcessor):
    """
    <summary>
    EventProcessor that appends chat messages to a JSONL training log when
    the chat_logging feature flag is enabled.
    </summary>
    """

    SUBSCRIPTIONS = {
        "twitch_chat_filtered": "handle_event",
        "kick_chat_filtered":   "handle_event",
        "stt_filtered":         "handle_event",
    }

    def __init__(self, runtime_state=None, log_path: Path = _LOG_PATH) -> None:
        """
        <summary>Initialise the logger.</summary>
        <param name="runtime_state">RuntimeState whose chat_logging flag is checked on every event.</param>
        <param name="log_path">Path to the JSONL output file. Defaults to logs/chat_training.jsonl.</param>
        """
        super().__init__("chat logger")
        self.runtime_state = runtime_state
        self.log_path = log_path

    async def handle_event(self, event) -> None:
        """
        <summary>
        Write a filtered chat event to the training log if chat_logging is enabled.
        </summary>
        <param name="event">A *_filtered chat or STT event from ConversationProcessor.</param>
        """
        if not self._is_logging_enabled():
            return

        source = _SOURCE_MAP.get(event.type, event.type)
        user = event.data.get("user") or ("streamer" if source == "stt" else "unknown")
        text = event.data.get("text", "").strip()

        if not text:
            return

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source":    source,
            "user":      user,
            "text":      text,
        }

        self._append(entry)
        self.logger.debug("[handle_event] Logged %s message from %s", source, user)

    def _is_logging_enabled(self) -> bool:
        """
        <summary>Return True if the chat_logging feature flag is currently on.</summary>
        """
        if self.runtime_state is None:
            return False
        return getattr(self.runtime_state.features, "chat_logging", False)

    def _append(self, entry: dict) -> None:
        """
        <summary>Append a single entry to the JSONL log file, creating it if needed.</summary>
        <param name="entry">Dict to serialise as a single JSON line.</param>
        """
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as exc:
            self.logger.error("[_append] Failed to write training log: %s", exc)
