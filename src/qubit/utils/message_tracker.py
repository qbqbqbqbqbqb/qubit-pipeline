from collections import deque
from datetime import datetime, timedelta, timezone


class MessageTracker:
    """
    Tracks messages to prevent repetition and manage responses.

    This class maintains a queue of recent messages, tracks when messages were last seen,
    and keeps a record of responded messages. It provides methods to add messages,
    check for repetitions, and perform cleanup based on configurable expiry times.

    """
    def __init__(self, maxlen=100, recent_expiry=60, response_expiry=60):
        """Initialize the MessageTracker.

        Args:
            maxlen (int): Maximum number of recent messages to keep in the queue. Defaults to 100.
            recent_expiry (int): Time in seconds after which a message is no longer considered recent. Defaults to 60.
            response_expiry (int): Time in seconds after which a responded message is forgotten. Defaults to 60.
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