"""Geocoding via Nominatim.

Searches a place name and returns the first match's label and coordinates.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

from trips.providers.errors import ProviderError
from trips.providers.http import request_with_retry

NOMINATIM_BASE_URL = "https://nominatim.openstreetmap.org/search"

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
    params = urllib.parse.urlencode({"q": query, "format": "json", "limit": 1})
    url = f"{NOMINATIM_BASE_URL}?{params}"

    def request_results() -> list[dict]:
        request = urllib.request.Request(url, headers={"User-Agent": "truck-routing"})
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

    try:
        results = request_with_retry(request_results, service_name="Place search")
    except urllib.error.HTTPError as exc:
        raise ProviderError(f"Place search could not complete this request ({exc.code}).") from exc
    except ValueError as exc:
        raise ProviderError(f"Geocoding returned invalid JSON: {exc}") from exc

    if not results:
        raise ProviderError(f"No place found for {query!r}.")

    first = results[0]
    return GeocodeResult(
        label=first.get("display_name", query),
        lat=float(first["lat"]),
        lon=float(first["lon"]),
    )
