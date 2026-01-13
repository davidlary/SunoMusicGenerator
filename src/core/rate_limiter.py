"""
Thread-safe rate limiter using token bucket algorithm.

This module implements a token bucket rate limiter to ensure API calls
stay within rate limits while maximizing throughput.
"""

import time
import threading
from typing import Optional
from dataclasses import dataclass, field

from .errors import RateLimitError
from .logger import get_logger

logger = get_logger(__name__)


@dataclass
class TokenBucket:
    """
    Thread-safe token bucket for rate limiting.

    The token bucket algorithm allows bursts while maintaining
    an average rate over time.

    Attributes:
        capacity: Maximum number of tokens (burst size)
        rate: Token refill rate (tokens per second)
        tokens: Current number of available tokens
        last_refill: Timestamp of last token refill
        lock: Thread lock for synchronization
    """

    capacity: float
    rate: float  # tokens per second
    tokens: float = field(init=False)
    last_refill: float = field(init=False)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self):
        """Initialize tokens and timestamp."""
        self.tokens = self.capacity
        self.last_refill = time.time()

    def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill

        # Add tokens based on elapsed time and rate
        self.tokens = min(
            self.capacity,
            self.tokens + (elapsed * self.rate)
        )
        self.last_refill = now

    def consume(self, tokens: float = 1.0, blocking: bool = True) -> bool:
        """
        Consume tokens from the bucket.

        Args:
            tokens: Number of tokens to consume
            blocking: If True, wait until tokens are available

        Returns:
            True if tokens were consumed, False if not available (non-blocking)

        Raises:
            RateLimitError: If tokens > capacity (invalid request)
        """
        if tokens > self.capacity:
            raise RateLimitError(
                f"Requested tokens ({tokens}) exceeds bucket capacity ({self.capacity})",
                details={"requested": tokens, "capacity": self.capacity}
            )

        with self.lock:
            self._refill()

            if self.tokens >= tokens:
                self.tokens -= tokens
                logger.debug(
                    f"Consumed {tokens} tokens",
                    remaining=self.tokens,
                    capacity=self.capacity
                )
                return True

            if not blocking:
                return False

            # Calculate wait time
            tokens_needed = tokens - self.tokens
            wait_time = tokens_needed / self.rate

            logger.debug(
                f"Rate limit: waiting {wait_time:.2f}s for tokens",
                tokens_needed=tokens_needed,
                current_tokens=self.tokens
            )

        # Wait outside the lock to allow other threads
        time.sleep(wait_time)

        # Try again after waiting
        with self.lock:
            self._refill()
            if self.tokens >= tokens:
                self.tokens -= tokens
                logger.debug(
                    f"Consumed {tokens} tokens after waiting",
                    remaining=self.tokens
                )
                return True

            # Should not happen, but handle just in case
            return False

    def get_available_tokens(self) -> float:
        """
        Get current number of available tokens.

        Returns:
            Number of available tokens
        """
        with self.lock:
            self._refill()
            return self.tokens

    def get_wait_time(self, tokens: float = 1.0) -> float:
        """
        Calculate wait time until tokens are available.

        Args:
            tokens: Number of tokens needed

        Returns:
            Wait time in seconds (0 if tokens available)
        """
        with self.lock:
            self._refill()
            if self.tokens >= tokens:
                return 0.0
            tokens_needed = tokens - self.tokens
            return tokens_needed / self.rate


class RateLimiter:
    """
    Rate limiter for API calls.

    Manages multiple token buckets for different API services.
    """

    def __init__(self):
        """Initialize rate limiter with service-specific buckets."""
        self.buckets = {}
        logger.info("Rate limiter initialized")

    def add_bucket(
        self,
        name: str,
        rpm: float,
        throttle: float = 0.80,
        burst_multiplier: float = 1.5
    ) -> TokenBucket:
        """
        Add a rate limiting bucket for a service.

        Args:
            name: Service name (e.g., "gemini", "suno")
            rpm: Requests per minute limit
            throttle: Throttle percentage (0-1), default 80%
            burst_multiplier: Burst capacity multiplier, default 1.5x

        Returns:
            Created TokenBucket instance
        """
        effective_rpm = rpm * throttle
        rate = effective_rpm / 60.0  # Convert to tokens per second
        capacity = rate * burst_multiplier  # Allow some burst

        bucket = TokenBucket(capacity=capacity, rate=rate)
        self.buckets[name] = bucket

        logger.info(
            f"Added rate limiter bucket: {name}",
            rpm_limit=rpm,
            effective_rpm=effective_rpm,
            throttle_percent=throttle * 100,
            rate_per_second=rate,
            burst_capacity=capacity
        )

        return bucket

    def get_bucket(self, name: str) -> Optional[TokenBucket]:
        """
        Get a rate limiting bucket by name.

        Args:
            name: Service name

        Returns:
            TokenBucket instance or None if not found
        """
        return self.buckets.get(name)

    def acquire(
        self,
        service: str,
        tokens: float = 1.0,
        blocking: bool = True
    ) -> bool:
        """
        Acquire tokens for an API call.

        Args:
            service: Service name (must be added first)
            tokens: Number of tokens to acquire
            blocking: If True, wait until tokens are available

        Returns:
            True if tokens acquired, False otherwise

        Raises:
            ValueError: If service bucket not found
        """
        bucket = self.buckets.get(service)
        if not bucket:
            raise ValueError(
                f"Rate limiter bucket '{service}' not found. "
                f"Available buckets: {list(self.buckets.keys())}"
            )

        return bucket.consume(tokens=tokens, blocking=blocking)

    def wait_time(self, service: str, tokens: float = 1.0) -> float:
        """
        Get wait time until tokens are available.

        Args:
            service: Service name
            tokens: Number of tokens needed

        Returns:
            Wait time in seconds

        Raises:
            ValueError: If service bucket not found
        """
        bucket = self.buckets.get(service)
        if not bucket:
            raise ValueError(
                f"Rate limiter bucket '{service}' not found"
            )

        return bucket.get_wait_time(tokens)

    def get_status(self, service: Optional[str] = None) -> dict:
        """
        Get rate limiter status.

        Args:
            service: Optional service name (all services if None)

        Returns:
            Status dictionary
        """
        if service:
            bucket = self.buckets.get(service)
            if not bucket:
                return {}

            return {
                "service": service,
                "available_tokens": bucket.get_available_tokens(),
                "capacity": bucket.capacity,
                "rate": bucket.rate,
                "utilization_pct": (
                    (bucket.capacity - bucket.get_available_tokens()) /
                    bucket.capacity * 100
                )
            }

        # Return status for all buckets
        return {
            name: {
                "available_tokens": bucket.get_available_tokens(),
                "capacity": bucket.capacity,
                "rate": bucket.rate,
            }
            for name, bucket in self.buckets.items()
        }


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """
    Get the global rate limiter instance.

    Returns:
        RateLimiter instance
    """
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def init_rate_limiter(gemini_rpm: float = 60, suno_rpm: float = 30) -> RateLimiter:
    """
    Initialize the global rate limiter with API limits.

    Args:
        gemini_rpm: Gemini requests per minute
        suno_rpm: Suno requests per minute

    Returns:
        Initialized RateLimiter instance
    """
    global _rate_limiter
    _rate_limiter = RateLimiter()

    # Add Gemini bucket (80% throttle)
    _rate_limiter.add_bucket("gemini", rpm=gemini_rpm, throttle=0.80)

    # Add Suno bucket (conservative 2-5 second delays)
    # Using RPM equivalent to 2-5 second delays
    _rate_limiter.add_bucket("suno", rpm=suno_rpm, throttle=1.0)

    logger.info(
        "Rate limiter initialized",
        gemini_rpm=gemini_rpm,
        suno_rpm=suno_rpm
    )

    return _rate_limiter
