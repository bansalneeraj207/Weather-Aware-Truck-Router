from datetime import datetime, timezone, timedelta

from trips.models import RouteOption, Trip
from trips.providers.errors import ProviderError
from trips.providers.geocoding import geocode
from trips.providers.routing import MAX_ROUTE_ALTERNATIVES, fetch_route_alternatives


from trips.sampling import SAMPLE_MILES, sample_checkpoints, polyline_distance_mi, segment_lengths_mi

SAMPLE_MILES = (10, 25, 50)

class PlanningError(Exception):
    """Raised when planning cannot complete (provider or validation failure)."""

FORECAST_HOURS = 48
WEATHER_FORECAST_UNAVAILABLE = "WEATHER_FORECAST_UNAVAILABLE"
ROUTES_UNAVAILABLE = "ROUTES_UNAVAILABLE"
OPEN_METEO_FORECAST_DAYS = 16

def plan_trip(
    *,
    start: str,
    end: str,
    load_lb: float,
    depart_at: datetime,
    sample_miles: int,
) -> dict:
    """Plan a trip."""
    
    if load_lb <= 0:
        raise PlanningError("Load weight must be greater than zero.")
    if sample_miles not in SAMPLE_MILES:
        raise PlanningError("Sample spacing must be 10, 25, or 50 miles.")
    if depart_at.tzinfo is None:
        raise PlanningError("Departure time must include a timezone.")
    depart_at = depart_at.astimezone(timezone.utc)

    try:
        origin = geocode(start)
        destination = geocode(end)
    except ProviderError as exc:
        raise PlanningError(str(exc)) from exc

    if (
        abs(origin.lat - destination.lat) < 1e-9
        and abs(origin.lon - destination.lon) < 1e-9
    ):
        raise PlanningError("Start and end resolve to the same point.")

    try:
        alternatives = fetch_route_alternatives(
            origin.lat,
            origin.lon,
            destination.lat,
            destination.lon,
            alternatives=MAX_ROUTE_ALTERNATIVES,
        )
    except ProviderError as exc:
        raise PlanningError(str(exc)) from exc

    trip = Trip.objects.create(
        start_label=origin.label,
        start_lat=origin.lat,
        start_lon=origin.lon,
        end_label=destination.label,
        end_lat=destination.lat,
        end_lon=destination.lon,
        load_lb=load_lb,
    )

    prepared = []
    for index, alternative in enumerate(alternatives):
        checkpoints = sample_checkpoints(alternative.coords, sample_miles)
        total_mi = checkpoints[-1]["distance_mi"] if checkpoints else 0.0
        for checkpoint in checkpoints:
            fraction = 0.0 if total_mi <= 0 else checkpoint["distance_mi"] / total_mi
            checkpoint["eta"] = depart_at + timedelta(
                hours=alternative.duration_hr * fraction
            )
        prepared.append(
            {
                "provider_route_index": index,
                "coords": alternative.coords,
                "distance_mi": None,
                "travel_time_hr": round(alternative.duration_hr, 4),
                "segment_count": alternative.segment_count,
                "checkpoints": checkpoints,
            }
        )

    latest_eta = max(
        checkpoint["eta"]
        for route in prepared
        for checkpoint in route["checkpoints"]
    )

    return {
        "start": {"label": origin.label, "lat": origin.lat, "lon": origin.lon},
        "end": {"label": destination.label, "lat": destination.lat, "lon": destination.lon},
        "depart_at": depart_at.isoformat(),
        "sample_miles": sample_miles,
        "load_lb": load_lb,
        "routes": prepared,
    }