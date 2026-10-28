"""Thread-safe manual clock for tests that cross process boundaries."""

import time
from collections.abc import Callable
from math import isfinite
from threading import Lock


class ManualClock:
    """Expose callable time that tests may advance without sleeping."""

    def __init__(
        self,
        time_source: Callable[[], float] = time.time,
    ) -> None:
        self._time_source = time_source
        self._offset = 0.0
        self._lock = Lock()

    def __call__(self) -> float:
        """Return the current test timestamp."""
        with self._lock:
            return self._time_source() + self._offset

    def advance(self, seconds: float) -> float:
        """Advance time by one finite, positive, bounded interval."""
        if not isfinite(seconds) or seconds <= 0 or seconds > 86400:
            raise ValueError("Browser time increment is out of range.")
        with self._lock:
            self._offset += seconds
            return self._time_source() + self._offset
