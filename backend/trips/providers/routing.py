import json
import math
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

from geographiclib.geodesic import Geodesic
import polyline

from trips.providers.errors import ProviderError
from trips.providers.http import request_with_retry

VALHALLA_ROUTE_URL = os.getenv(
    "VALHALLA_ROUTE_URL", "https://valhalla1.openstreetmap.de/route"
)
VALHALLA_CLIENT_ID = os.getenv(
    "VALHALLA_CLIENT_ID", "weather-aware-truck-router-local"
)
MAX_ROUTE_ALTERNATIVES = 3
# Valhalla rejects requests at roughly 1,500 km. Keep individual legs below
# that ceiling so a real road detour still has headroom.
MAX_LEG_DISTANCE_METERS = 1_200_000
_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "WeatherAwareTruckRouter/1.0",
    "X-Client-Id": VALHALLA_CLIENT_ID,
}

# use_highways=1 is the strongest highway preference Valhalla accepts.
# Living streets and tracks are avoided; service roads take a transition penalty.
TRUCK_COSTING = {
    "use_highways": 1,
    "use_tolls": 1,
    "use_living_streets": 0,
    "use_tracks": 0,
    "service_penalty": 30,
}

@dataclass
class RouteResult:
    """One driving alternative from the routing provider."""

    coords: list[list[float]]  # [[lon, lat], ...]
    distance_mi: float
    duration_hr: float
    segment_count: int = 1

def decode_polyline6(encoded: str) -> list[list[float]]:
    """Decode a Valhalla polyline (precision 1e-6) into [lon, lat] pairs."""
    return [list(point) for point in polyline.decode(encoded, precision=6, geojson=True)]


def routes_from_payload(data: dict) -> list[RouteResult]:
    """Turn a Valhalla route response into route results, capped at three."""
    if data.get("error"):
        raise ProviderError(str(data["error"]))

    trips: list[dict] = []
    if isinstance(data.get("trip"), dict):
        trips.append(data["trip"])
    for alternate in data.get("alternates") or []:
        trip = alternate.get("trip") if isinstance(alternate, dict) else None
        if isinstance(trip, dict):
            trips.append(trip)

    results: list[RouteResult] = []
    for trip in trips:
        coords: list[list[float]] = []
        for leg in trip.get("legs") or []:
            coords.extend(decode_polyline6(leg.get("shape") or ""))
        if len(coords) < 2:
            continue
        summary = trip.get("summary") or {}
        length = summary.get("length")
        seconds = summary.get("time")
        if length is None or seconds is None:
            continue
        results.append(
            RouteResult(
                coords=coords,
                distance_mi=float(length),
                duration_hr=float(seconds) / 3600.0,
            )
        )

    if not results:
        raise ProviderError("Routing service returned no routes for these points.")
    return results[:MAX_ROUTE_ALTERNATIVES]


def fetch_route_alternatives(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    alternatives: int = MAX_ROUTE_ALTERNATIVES,
) -> list[RouteResult]:
    """Fetch truck route alternatives between two coordinates.

    Raises ProviderError when the service is unreachable or returns no route.
    The service may return fewer alternatives than requested; the result is
    capped at ``MAX_ROUTE_ALTERNATIVES``.
    """
    points = [(start_lat, start_lon), (end_lat, end_lon)]
    # A long trip has a single stitched route. Alternatives across independent
    # legs would not be meaningful without evaluating every combination.
    if _distance_meters(*points) > MAX_LEG_DISTANCE_METERS:
        return _fetch_segmented_route(points)

    requested = max(1, min(alternatives, MAX_ROUTE_ALTERNATIVES))
    try:
        return routes_from_payload(_request_route(points, alternates=requested - 1))
    except ProviderError as exc:
        # Road distance can be much larger than the straight-line estimate
        # (mountains, coastlines, or sparse road networks). Retry as legs only
        # for the provider's known maximum-distance response.
        if _is_distance_limit_error(exc):
            return _fetch_segmented_route(points)
        raise


def _fetch_segmented_route(
    endpoints: list[tuple[float, float]],
) -> list[RouteResult]:
    """Route each safe-sized leg, then stitch the results into one option."""
    points = _segment_points(*endpoints)
    legs: list[RouteResult] = []
    for start, end in zip(points, points[1:]):
        results = routes_from_payload(_request_route([start, end], alternates=0))
        legs.append(results[0])

    geometry: list[list[float]] = []
    for leg in legs:
        if geometry and leg.coords and geometry[-1] == leg.coords[0]:
            geometry.extend(leg.coords[1:])
        else:
            geometry.extend(leg.coords)
    return [
        RouteResult(
            coords=geometry,
            distance_mi=sum(leg.distance_mi for leg in legs),
            duration_hr=sum(leg.duration_hr for leg in legs),
            segment_count=len(legs),
        )
    ]


def _distance_meters(
    start: tuple[float, float], end: tuple[float, float]
) -> float:
    return Geodesic.WGS84.Inverse(*start, *end)["s12"]


def _segment_points(
    start: tuple[float, float], end: tuple[float, float]
) -> list[tuple[float, float]]:
    """Return endpoints plus geodesic waypoints for safe-sized route legs."""
    line = Geodesic.WGS84.InverseLine(*start, *end)
    leg_count = max(2, math.ceil(line.s13 / MAX_LEG_DISTANCE_METERS))
    points = [start]
    for leg_number in range(1, leg_count):
        position = line.Position(line.s13 * leg_number / leg_count)
        points.append((position["lat2"], position["lon2"]))
    points.append(end)
    return points


def _is_distance_limit_error(error: ProviderError) -> bool:
    message = str(error).lower()
    return "1500000" in message or (
        "distance" in message
        and any(word in message for word in ("maximum", "exceed", "limit", "too long"))
    )


def _request_route(points: list[tuple[float, float]], *, alternates: int) -> dict:
    body: dict = {
        "locations": [{"lat": lat, "lon": lon} for lat, lon in points],
        "costing": "truck",
        "costing_options": {"truck": TRUCK_COSTING},
        "units": "miles",
    }
    if alternates > 0:
        body["alternates"] = alternates

    def request_route() -> dict:
        request = urllib.request.Request(
            VALHALLA_ROUTE_URL,
            data=json.dumps(body).encode("utf-8"),
            headers=_HEADERS,
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)

    try:
        data = request_with_retry(request_route, service_name="Routing service")
    except urllib.error.HTTPError as exc:
        try:
            message = json.load(exc).get("error")
        except (AttributeError, OSError, ValueError):
            message = None
        raise ProviderError(
            f"Routing service rejected this trip: {message or exc.reason}"
        ) from exc
    except ValueError as exc:
        raise ProviderError(f"Routing service returned invalid JSON: {exc}") from exc
    return data
