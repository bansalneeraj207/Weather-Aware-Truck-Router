"""Geocoding via Nominatim.

Searches a place name and returns the first match's label and coordinates.
"""

import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request

from django.core.cache import cache

from trips.providers.errors import ProviderError
from trips.providers.http import ThreadSafeRateLimiter, request_with_retry

NOMINATIM_BASE_URL = os.getenv(
    "NOMINATIM_BASE_URL", "https://nominatim.openstreetmap.org/search"
)
PROVIDER_USER_AGENT = os.getenv(
    "PROVIDER_USER_AGENT", "WeatherAwareTruckRouter/1.0 (local development)"
)
GEOCODING_CACHE_SECONDS = int(os.getenv("GEOCODING_CACHE_SECONDS", "604800"))
NOMINATIM_RATE_LIMITER = ThreadSafeRateLimiter(1.0)


class GeocodeResult:
    """A resolved place: display label plus lat/lon."""

    def __init__(self, label: str, lat: float, lon: float) -> None:
        self.label = label
        self.lat = lat
        self.lon = lon


def geocode(query: str) -> GeocodeResult:
    """Resolve a place name to coordinates.

    Raises ProviderError when the service is unreachable or finds nothing.
    """
    normalized_query = " ".join(query.strip().casefold().split())
    cache_key = "geocode:" + hashlib.sha256(normalized_query.encode("utf-8")).hexdigest()
    cached = cache.get(cache_key)
    if isinstance(cached, dict):
        return GeocodeResult(cached["label"], cached["lat"], cached["lon"])

    params = urllib.parse.urlencode({"q": query, "format": "json", "limit": 1})
    url = f"{NOMINATIM_BASE_URL}?{params}"

    def request_results() -> list[dict]:
        # This sits inside the retry operation so every outbound attempt is
        # rate-limited, including retries from request_with_retry().
        request = urllib.request.Request(
            url, headers={"User-Agent": PROVIDER_USER_AGENT}
        )

        def send() -> list[dict]:
            with urllib.request.urlopen(request, timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))

        return NOMINATIM_RATE_LIMITER.run(send)

    try:
        results = request_with_retry(request_results, service_name="Place search")
    except urllib.error.HTTPError as exc:
        raise ProviderError(f"Place search could not complete this request ({exc.code}).") from exc
    except ValueError as exc:
        raise ProviderError(f"Geocoding returned invalid JSON: {exc}") from exc

    if not results:
        raise ProviderError(f"No place found for {query!r}.")

    first = results[0]
    result = GeocodeResult(
        label=first.get("display_name", query),
        lat=float(first["lat"]),
        lon=float(first["lon"]),
    )
    cache.set(
        cache_key,
        {"label": result.label, "lat": result.lat, "lon": result.lon},
        GEOCODING_CACHE_SECONDS,
    )
    return result
