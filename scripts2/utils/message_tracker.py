import datetime
from collections import deque

class MessageTracker:
    def __init__(self, maxlen=100, recent_expiry=60, response_expiry=60):
        self.recent_messages = deque(maxlen=maxlen)
        self.last_seen = {}
        self.responded = {}
        self.recent_expiry = recent_expiry
        self.response_expiry = response_expiry

    def add_message(self, text):
        now = datetime.datetime.now(datetime.timezone.utc)
        self.recent_messages.append((text, now))
        self.last_seen[text] = now

    def is_repeated(self, text) -> bool:
        now = datetime.datetime.now(datetime.timezone.utc)
        return text in self.last_seen and (now - self.last_seen[text]).total_seconds() < self.recent_expiry

    def add_responded(self, text):
        self.responded[text] = datetime.datetime.now(datetime.timezone.utc)

    def is_responded(self, text) -> bool:
        return text in self.responded

    def cleanup(self):
        self._cleanup_recent_messages()
        self._cleanup_responded_messages()

    def _cleanup_recent_messages(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        while self.recent_messages and (now - self.recent_messages[0][1]).total_seconds() > self.recent_expiry:
            old_text, _ = self.recent_messages.popleft()
            if old_text in self.last_seen:
                del self.last_seen[old_text]

    def _cleanup_responded_messages(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        expired = [text for text, ts in self.responded.items()
                if (now - ts).total_seconds() > self.response_expiry]
        for text in expired:
            del self.responded[text]