"""Small, dependency-free reliability helpers for public data providers."""

from __future__ import annotations

import threading
import time
import urllib.error
from collections.abc import Callable
from typing import TypeVar

from trips.providers.errors import ProviderError

T = TypeVar("T")
RETRY_ATTEMPTS = 2


class ThreadSafeRateLimiter:
    """Serialize and space outbound attempts across threads in this process."""

    def __init__(self, minimum_interval_seconds: float) -> None:
        if minimum_interval_seconds < 0:
            raise ValueError("minimum_interval_seconds must be non-negative")
        self.minimum_interval_seconds = minimum_interval_seconds
        self._lock = threading.Lock()
        self._last_attempt_started: float | None = None

    def run(self, operation: Callable[[], T]) -> T:
        """Run an outbound operation only after the next attempt slot opens."""
        with self._lock:
            now = time.monotonic()
            if self._last_attempt_started is not None:
                delay = (
                    self._last_attempt_started
                    + self.minimum_interval_seconds
                    - now
                )
                if delay > 0:
                    time.sleep(delay)
                    now = time.monotonic()
            self._last_attempt_started = now
            # Keep the lock through the call so another thread cannot begin an
            # attempt if this one is descheduled just before opening its socket.
            return operation()


def request_with_retry(operation: Callable[[], T], *, service_name: str) -> T:
    """Retry one transient network failure, then return an actionable error."""
    last_error: Exception | None = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            return operation()
        except urllib.error.HTTPError:
            # A provider response is not a transient connection failure. Let
            # each provider translate it into its most useful message.
            raise
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt + 1 < RETRY_ATTEMPTS:
                time.sleep(0.25)
    raise ProviderError(
        f"{service_name} is temporarily unavailable. Please try again shortly."
    ) from last_error
