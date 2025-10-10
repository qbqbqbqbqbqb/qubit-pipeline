import datetime

class TokenBucketLimiter:
    def __init__(self, rate: float, burst: int):
        self.rate = rate
        self.burst = burst
        self.tokens = burst
        self.last_checked = datetime.datetime.now(datetime.timezone.utc)

    def allow(self) -> bool:
        now = datetime.datetime.now(datetime.timezone.utc)
        elapsed = (now - self.last_checked).total_seconds()
        self.last_checked = now
        self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False
