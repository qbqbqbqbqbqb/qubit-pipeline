import datetime
from collections import deque

"""
MessageTracker utility for tracking messages and preventing repetition.

This module provides the MessageTracker class which helps manage recent messages,
detect repetitions, and track responded messages with automatic cleanup.
"""
class MessageTracker:
    """
    Tracks messages to prevent repetition and manage responses.

    This class maintains a queue of recent messages, tracks when messages were last seen,
    and keeps a record of responded messages. It provides methods to add messages,
    check for repetitions, and perform cleanup based on configurable expiry times.

    Attributes:
        recent_messages (deque): Queue of tuples (text, timestamp) for recent messages.
        last_seen (dict): Maps message text to the last seen timestamp.
        responded (dict): Maps message text to the responded timestamp.
        recent_expiry (int): Seconds after which a message is no longer considered recent.
        response_expiry (int): Seconds after which a responded message is forgotten.
    """
    def __init__(self, maxlen=100, recent_expiry=60, response_expiry=60):
        """Initialize the MessageTracker.

        Args:
            maxlen (int): Maximum number of recent messages to keep in the queue. Defaults to 100.
            recent_expiry (int): Time in seconds after which a message is no longer considered recent. Defaults to 60.
            response_expiry (int): Time in seconds after which a responded message is forgotten. Defaults to 60.
        """
        self.recent_messages = deque(maxlen=maxlen)
        self.last_seen = {}
        self.responded = {}
        self.recent_expiry = recent_expiry
        self.response_expiry = response_expiry

    def add_message(self, text):
        """Add a message to the recent messages queue and update last seen time.

        Args:
            text (str): The message text to add.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        self.recent_messages.append((text, now))
        self.last_seen[text] = now

    def is_repeated(self, text) -> bool:
        """Check if the given message text is a recent repetition.

        Args:
            text (str): The message text to check.

        Returns:
            bool: True if the message is considered a repetition, False otherwise.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        return text in self.last_seen and (now - self.last_seen[text]).total_seconds() < self.recent_expiry

    def add_responded(self, text):
        """Mark a message as responded to.

        Args:
            text (str): The message text that was responded to.
        """
        self.responded[text] = datetime.datetime.now(datetime.timezone.utc)

    def is_responded(self, text) -> bool:
        """Check if the given message has already been responded to.

        Args:
            text (str): The message text to check.

        Returns:
            bool: True if the message has been responded to, False otherwise.
        """
        return text in self.responded

    def cleanup(self):
        """Perform cleanup of expired recent and responded messages."""
        self._cleanup_recent_messages()
        self._cleanup_responded_messages()

    def _cleanup_recent_messages(self):
        """Remove expired messages from the recent messages queue and last_seen dict."""
        now = datetime.datetime.now(datetime.timezone.utc)
        while self.recent_messages and (now - self.recent_messages[0][1]).total_seconds() > self.recent_expiry:
            old_text, _ = self.recent_messages.popleft()
            if old_text in self.last_seen:
                del self.last_seen[old_text]

    def _cleanup_responded_messages(self):
        """Remove expired responded messages from the responded dict."""
        now = datetime.datetime.now(datetime.timezone.utc)
        expired = [text for text, ts in self.responded.items()
                if (now - ts).total_seconds() > self.response_expiry]
        for text in expired:
            del self.responded[text]