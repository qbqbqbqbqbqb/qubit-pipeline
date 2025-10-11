import datetime

"""
Module for rate limiting utilities.

This module provides classes for implementing rate limiting mechanisms,
such as the Token Bucket algorithm.
"""

class TokenBucketLimiter:
    """Implements a token bucket rate limiter.

    The token bucket algorithm allows for bursty traffic while maintaining
    an average rate limit. Tokens are added to the bucket at a constant rate,
    and requests consume tokens.

    Attributes:
        rate (float): Tokens added per second.
        burst (int): Maximum tokens in the bucket.
        tokens (float): Current tokens available.
        last_checked (datetime): Last time tokens were checked/updated.
    """
    def __init__(self, rate: float, burst: int):
        """Initialize the TokenBucketLimiter.

        Args:
            rate (float): The rate at which tokens are added per second.
            burst (int): The maximum number of tokens the bucket can hold.
        """
        self.rate = rate
        self.burst = burst
        self.tokens = burst
        self.last_checked = datetime.datetime.now(datetime.timezone.utc)

    def allow(self) -> bool:
        """Check if a request is allowed based on available tokens.

        Updates the token count based on elapsed time and checks if
        at least one token is available.

        Returns:
            bool: True if the request is allowed, False otherwise.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        elapsed = (now - self.last_checked).total_seconds()
        self.last_checked = now
        self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False
