"""Small, dependency-free reliability helpers for public data providers."""

from __future__ import annotations

import time
import urllib.error
from collections.abc import Callable
from typing import TypeVar

from trips.providers.errors import ProviderError

T = TypeVar("T")
RETRY_ATTEMPTS = 2


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
