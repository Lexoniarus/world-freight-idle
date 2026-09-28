"""Provider-owned concurrency, pacing and Retry-After handling."""

import asyncio
import math
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from email.utils import parsedate_to_datetime


def retry_after_seconds(value: str | None, now: float) -> float:
    """Parse HTTP delay seconds or an HTTP date without inventing retries."""
    if not value:
        return 0.0
    try:
        delay = float(value)
    except ValueError:
        try:
            delay = parsedate_to_datetime(value).timestamp() - now
        except (ValueError, TypeError, OverflowError):
            return 0.0
    return max(0.0, delay) if math.isfinite(delay) else 0.0


class ProviderRequestLimiter:
    """Share one bounded resource across a provider's HTTP adapters."""

    def __init__(self, concurrency: int, minimum_interval: float) -> None:
        """Reject invalid limits before allocating asynchronous resources."""
        if concurrency < 1 or not math.isfinite(minimum_interval):
            raise ValueError("Invalid provider request limits.")
        if minimum_interval < 0:
            raise ValueError("Provider interval cannot be negative.")
        self._semaphore = asyncio.Semaphore(concurrency)
        self._lock = asyncio.Lock()
        self._interval = minimum_interval
        self._next_request = 0.0

    @asynccontextmanager
    async def request(self) -> AsyncIterator[None]:
        """Reserve concurrency and pace starts, releasing on cancellation."""
        async with self._semaphore:
            async with self._lock:
                while self._next_request > time.monotonic():
                    await asyncio.sleep(self._next_request - time.monotonic())
                self._next_request = time.monotonic() + self._interval
            yield

    def defer(self, retry_after: str | None) -> None:
        """Apply Retry-After to all subsequent requests for this provider."""
        delay = retry_after_seconds(retry_after, time.time())
        self._next_request = max(self._next_request, time.monotonic() + delay)
