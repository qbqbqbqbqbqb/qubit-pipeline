"""
<summary>
MessageTracker — short-term deduplication utility for input messages.
</summary>
<remarks>
Used by ConversationProcessor to avoid reacting to the same chat or STT message
more than once within a configurable time window.
</remarks>
"""

from datetime import datetime, timezone


class MessageTracker:
    """
    <summary>
    Tracks the last-seen timestamp per message text and reports whether a
    message is a recent repeat within the configured expiry window.
    </summary>
    """

    def __init__(self, maxlen: int = 100, recent_expiry: int = 60, response_expiry: int = 60):
        """
        <summary>Initialise the tracker with expiry windows.</summary>
        <param name="maxlen">Reserved for future bounded-queue support. Currently unused.</param>
        <param name="recent_expiry">Seconds after which a message is no longer considered recent for deduplication.</param>
        <param name="response_expiry">Seconds after which a responded-to message can be forgotten.</param>
        """
        self.last_seen: dict = {}
        self.recent_expiry = recent_expiry
        self.response_expiry = response_expiry

    def add_message(self, text: str) -> None:
        """
        <summary>Record the current time as the last-seen timestamp for this message text.</summary>
        <param name="text">The message text to record.</param>
        """
        self.last_seen[text] = datetime.now(timezone.utc)

    def is_repeated(self, text: str) -> bool:
        """
        <summary>Return True if this message text was seen within the recent_expiry window.</summary>
        <param name="text">The message text to check.</param>
        <returns>True if the message is a recent duplicate.</returns>
        """
        now = datetime.now(timezone.utc)
        return text in self.last_seen and (now - self.last_seen[text]).total_seconds() < self.recent_expiry
