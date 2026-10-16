from datetime import datetime, timezone
from trips.providers.geocoding import geocode
from trips.providers.errors import ProviderError

SAMPLE_MILES = (10, 25, 50)

class PlanningError(Exception):
    """Raised when planning cannot complete (provider or validation failure)."""

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
        
    return {
        "start": {"label": origin.label, "lat": origin.lat, "lon": origin.lon},
        "end": {"label": destination.label, "lat": destination.lat, "lon": destination.lon},
        "depart_at": depart_at.isoformat(),
        "sample_miles": sample_miles,
    }