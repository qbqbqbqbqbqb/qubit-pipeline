from collections import deque
from datetime import datetime, timedelta, timezone


class MessageTracker:
    """
    Utility for short-term deduplication of input messages.

    Used by cognitive/processing layers to avoid reacting to the same
    chat/STT message multiple times within a configurable window.

    Responsibilities:
    - Track last-seen time per message text
    - Report whether a message is a recent repeat (is_repeated)
    - (Future) track which messages have already received a response

    Part of the 2026 refactor: extracted as a pure utility so that
    decision logic in ActivityTracker / DecisionEngine stays clean.
    """

    def __init__(self, maxlen=100, recent_expiry=60, response_expiry=60):
        """
        Initialize the MessageTracker.

        Args:
            maxlen (int): Maximum number of recent messages to keep (currently unused; reserved for future queue).
            recent_expiry (int): Seconds after which a message is no longer considered "recent" for dedup.
            response_expiry (int): Seconds after which a responded-to message can be forgotten.
        """
        self.last_seen = {}
        self.recent_expiry = recent_expiry
        self.response_expiry = response_expiry

    def add_message(self, text):
        """Add a message to the recent messages queue and update last seen time.

        Args:
            text (str): The message text to add.
        """
        now = datetime.now(timezone.utc)
        self.last_seen[text] = now

    def is_repeated(self, text) -> bool:
        """Check if the given message text is a recent repetition.

        Args:
            text (str): The message text to check.

        Returns:
            bool: True if the message is considered a repetition, False otherwise.
        """
        now = datetime.now(timezone.utc)
        return text in self.last_seen and (now - self.last_seen[text]).total_seconds() < self.recent_expiry