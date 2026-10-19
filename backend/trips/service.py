from datetime import datetime, timedelta, timezone

from trips.models import RouteOption, Trip
from trips.providers.errors import ProviderError
from trips.providers.geocoding import geocode
from trips.providers.routing import MAX_ROUTE_ALTERNATIVES, fetch_route_alternatives
from trips.providers.weather import fetch_hourly_forecast, HourlyForecast

from trips.sampling import SAMPLE_MILES, sample_checkpoints, polyline_distance_mi, segment_lengths_mi

from risk.checkpoint import CheckpointRiskAssessment, assess_checkpoint
from risk.recommendation import (
    InvalidRouteError,
    RecommendationStatus,
    Route,
    RouteRecommendationResult,
    RouteRiskMetrics,
    RouteSegmentSpec,
    recommend_routes,
)


class PlanningError(Exception):
    """Raised when planning cannot complete (provider or validation failure)."""

FORECAST_HOURS = 48
WEATHER_FORECAST_UNAVAILABLE = "WEATHER_FORECAST_UNAVAILABLE"
ROUTES_UNAVAILABLE = "ROUTES_UNAVAILABLE"
OPEN_METEO_FORECAST_DAYS = 16

def _forecast_window_end(end: datetime, *, now: datetime | None = None) -> datetime:
    """Clamp a requested window to the last day Open-Meteo can forecast."""
    reference = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).date()
    # A 16-day forecast includes today plus the following 15 calendar days.
    last_available_date = reference + timedelta(days=OPEN_METEO_FORECAST_DAYS - 1)
    last_available_moment = datetime.combine(
        last_available_date, datetime.max.time(), tzinfo=timezone.utc
    )
    return min(end.astimezone(timezone.utc), last_available_moment)

def _assess_at(
    forecasts: dict[tuple[float, float], HourlyForecast],
    checkpoint: dict,
    load_lb: float,
) -> CheckpointRiskAssessment:
    reading = forecasts[_forecast_key(checkpoint["lat"], checkpoint["lon"])].at(
        checkpoint["eta"]
    )
    return assess_checkpoint(
        wind_mph=reading.wind_mph,
        rain_in_hr=reading.rain_in_hr,
        snow_in_hr=reading.snow_in_hr,
        load_lb=load_lb,
    )

def _unknown_assessment(load_lb: float) -> CheckpointRiskAssessment:
    """An explicit unknown assessment when the provider has no forecast horizon."""
    return assess_checkpoint(
        wind_mph=None,
        rain_in_hr=None,
        snow_in_hr=None,
        load_lb=load_lb,
    )


def _weather_unavailable_at(
    forecasts: dict[tuple[float, float], HourlyForecast], checkpoint: dict
) -> bool:
    """Whether the provider returned no weather at this checkpoint's ETA."""
    reading = forecasts[_forecast_key(checkpoint["lat"], checkpoint["lon"])].at(
        checkpoint["eta"]
    )
    return (
        reading.wind_mph is None
        and reading.rain_in_hr is None
        and reading.snow_in_hr is None
    )


def _heatmap(
    prepared: list[dict],
    forecasts: dict[tuple[float, float], HourlyForecast],
    depart_at: datetime,
    load_lb: float,
) -> dict:
    """Risk at each checkpoint for every hour from departure through +48 h."""
    points = []
    for route in prepared:
        for checkpoint in route["checkpoints"]:
            forecast = forecasts[_forecast_key(checkpoint["lat"], checkpoint["lon"])]
            severities = []
            wind_mph = []
            rain_in_hr = []
            snow_in_hr = []
            for hour in range(FORECAST_HOURS + 1):
                moment = depart_at + timedelta(hours=hour)
                reading = forecast.at(moment)
                assessment = assess_checkpoint(
                    wind_mph=reading.wind_mph,
                    rain_in_hr=reading.rain_in_hr,
                    snow_in_hr=reading.snow_in_hr,
                    load_lb=load_lb,
                )
                severities.append(
                    None
                    if assessment.final_severity is None
                    else assessment.final_severity.name
                )
                wind_mph.append(reading.wind_mph)
                rain_in_hr.append(reading.rain_in_hr)
                snow_in_hr.append(reading.snow_in_hr)
            points.append(
                {
                    "lat": checkpoint["lat"],
                    "lon": checkpoint["lon"],
                    "severity": severities,
                    "wind_mph": wind_mph,
                    "rain_in_hr": rain_in_hr,
                    "snow_in_hr": snow_in_hr,
                }
            )
    return {"hours": FORECAST_HOURS, "points": points}


def _unknown_heatmap(prepared: list[dict]) -> dict:
    return {
        "hours": FORECAST_HOURS,
        "points": [
            {
                "lat": checkpoint["lat"],
                "lon": checkpoint["lon"],
                "severity": [None] * (FORECAST_HOURS + 1),
                "wind_mph": [None] * (FORECAST_HOURS + 1),
                "rain_in_hr": [None] * (FORECAST_HOURS + 1),
                "snow_in_hr": [None] * (FORECAST_HOURS + 1),
            }
            for route in prepared
            for checkpoint in route["checkpoints"]
        ],
    }

def _forecasts_for(
    prepared: list[dict],
    start: datetime,
    end: datetime,
) -> dict[tuple[float, float], HourlyForecast] | None:
    keys: list[tuple[float, float]] = []
    seen: set[tuple[float, float]] = set()
    for route in prepared:
        for checkpoint in route["checkpoints"]:
            key = _forecast_key(checkpoint["lat"], checkpoint["lon"])
            if key not in seen:
                seen.add(key)
                keys.append(key)
    try:
        forecasts = fetch_hourly_forecast(keys, start, end)
    except ProviderError as exc:
        raise PlanningError(str(exc)) from exc
    if len(forecasts) != len(keys):
        raise PlanningError("Weather service returned no forecast for this trip.")
    return dict(zip(keys, forecasts))

def _forecast_key(lat: float, lon: float) -> tuple[float, float]:
    return (round(lat, 2), round(lon, 2))


def _engine_routes(prepared: list[dict]) -> list[Route]:
    routes: list[Route] = []
    for prepared_route in prepared:
        lengths = segment_lengths_mi(prepared_route["checkpoints"])
        specs = [
            RouteSegmentSpec(
                length_mi=round(lengths[position], 4),
                assessment=prepared_route["assessments"][position],
            )
            for position in range(len(lengths))
        ]
        routes.append(
            Route.build(
                route_id=str(prepared_route["provider_route_index"]),
                distance_mi=prepared_route["distance_mi"],
                travel_time_hr=prepared_route["travel_time_hr"],
                segments=specs,
            )
        )
    return routes


def plan_trip(
    *,
    start: str,
    end: str,
    load_lb: float,
    depart_at: datetime,
    sample_miles: int,
) -> dict:
    """Plan a trip and persist it; returns the API response payload."""
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

    window_end = max(depart_at + timedelta(hours=FORECAST_HOURS), latest_eta)
    forecast_end = _forecast_window_end(window_end)
    # Do not make an invalid request when the departure itself is past the
    # provider horizon. Otherwise request every hour that is still available;
    # HourlyForecast.at() turns later ETA reads into explicit UNKNOWN values.
    forecast_unavailable = forecast_end < depart_at
    if forecast_unavailable:
        forecasts = None
    else:
        try:
            forecasts = _forecasts_for(prepared, depart_at, forecast_end)
        except PlanningError:
            trip.delete()
            raise

    # A partial forecast is based on the data returned for the end of each
    # route, rather than assuming that a calendar cutoff made it partial.
    forecast_partial = forecasts is not None and any(
        _weather_unavailable_at(forecasts, route["checkpoints"][-1])
        for route in prepared
    )

    for route in prepared:
        checkpoints = route["checkpoints"]
        assessments: list[CheckpointRiskAssessment] = (
            [_unknown_assessment(load_lb) for _ in checkpoints]
            if forecasts is None
            else [_assess_at(forecasts, checkpoint, load_lb) for checkpoint in checkpoints]
        )

        if len(assessments) < 2:
            assessments = assessments * 2
            checkpoints = checkpoints * 2
            route["checkpoints"] = checkpoints

        # Segment lengths must sum to the polyline distance the checkpoints
        # were sampled from, which is not the provider's own road distance.
        polyline_total_mi = polyline_distance_mi(route["coords"])
        last_checkpoint_mi = checkpoints[-1]["distance_mi"]
        if abs(last_checkpoint_mi - polyline_total_mi) > 0.5:
            trip.delete()
            raise PlanningError("Route geometry from provider was unusable for sampling.")

        route["distance_mi"] = round(last_checkpoint_mi, 4)
        route["assessments"] = assessments

    try:
        routes = _engine_routes(prepared)
    except InvalidRouteError as exc:
        trip.delete()
        raise PlanningError(f"Route data from provider was inconsistent: {exc}") from exc

    result = recommend_routes(routes)
    heatmap = (
        _unknown_heatmap(prepared)
        if forecasts is None
        else _heatmap(prepared, forecasts, depart_at, load_lb)
    )

    return _persist_and_respond(
        trip,
        prepared,
        result,
        depart_at=depart_at,
        sample_miles=sample_miles,
        heatmap=heatmap,
        forecast_unavailable=forecast_unavailable,
        forecast_partial=forecast_partial,
    )

def _persist_and_respond(
    trip: Trip,
    prepared: list[dict],
    result,
    *,
    depart_at: datetime,
    sample_miles: int,
    heatmap: dict,
    forecast_unavailable: bool = False,
    forecast_partial: bool = False,
) -> dict:
    """Save each alternative with its rank/metrics and build the response."""
    recommended_index: int | None = None
    if not forecast_unavailable and result.recommended_route is not None:
        recommended_index = int(result.recommended_route.route_id)

    ranked_by_index = {
        int(ranked.route.route_id): ranked for ranked in result.ranked_routes
    }
    ineligible_by_index = {
        int(entry.route.route_id): entry for entry in result.ineligible_routes
    }

    routes_payload: list[dict] = []
    for prepared_route in prepared:
        index = prepared_route["provider_route_index"]
        ranked = ranked_by_index.get(index)
        ineligible = ineligible_by_index.get(index)

        option = RouteOption.objects.create(
            trip=trip,
            provider_route_index=index,
            distance_mi=prepared_route["distance_mi"],
            travel_time_hr=prepared_route["travel_time_hr"],
            geometry=prepared_route["coords"],
            checkpoints=_serialize_checkpoints(prepared_route),
            metrics=_metrics_dict(
                ranked.metrics if ranked is not None else ineligible.metrics
            ),
            rank=None if forecast_unavailable else (ranked.rank if ranked is not None else None),
            is_recommended=not forecast_unavailable and index == recommended_index,
            ineligible_reason=",".join(ineligible.reason_codes) if ineligible else "",
        )

        routes_payload.append(
            {
                "provider_route_index": index,
                "distance_mi": option.distance_mi,
                "travel_time_hr": option.travel_time_hr,
                "geometry": option.geometry,
                "checkpoints": option.checkpoints,
                "metrics": option.metrics,
                "rank": option.rank,
                "is_recommended": option.is_recommended,
                "reason_codes": [WEATHER_FORECAST_UNAVAILABLE] if forecast_unavailable else (list(ranked.reason_codes) if ranked is not None else (
                    list(ineligible.reason_codes) if ineligible is not None else []
                )),
                "segment_count": prepared_route["segment_count"],
            }
        )

    return {
        "id": trip.id,
        "start": {"label": trip.start_label, "lat": trip.start_lat, "lon": trip.start_lon},
        "end": {"label": trip.end_label, "lat": trip.end_lat, "lon": trip.end_lon},
        "load_lb": trip.load_lb,
        "depart_at": depart_at.isoformat(),
        "sample_miles": sample_miles,
        "heatmap": heatmap,
        "weather_forecast_partial": forecast_partial,
        "routing_segments": max(route["segment_count"] for route in prepared),
        "status": WEATHER_FORECAST_UNAVAILABLE if forecast_unavailable else str(result.status),
        "recommended_route_index": recommended_index,
        "reason_codes": (
            [WEATHER_FORECAST_UNAVAILABLE]
            if forecast_unavailable
            else list(result.reason_codes)
        ),
        "explanations": (
            [
                "Weather forecast is unavailable this far ahead. Routes are shown, "
                "but weather risk and a recommendation cannot be calculated."
            ]
            if forecast_unavailable
            else list(result.explanations)
        ),
        "routes": routes_payload,
    }


def _serialize_checkpoints(prepared_route: dict) -> list[dict]:
    """Compact JSON form of each checkpoint for storage and map display."""
    serialized = []
    for checkpoint, assessment in zip(
        prepared_route["checkpoints"], prepared_route["assessments"]
    ):
        serialized.append(
            {
                "lat": checkpoint["lat"],
                "lon": checkpoint["lon"],
                "distance_mi": round(checkpoint["distance_mi"], 4),
                "eta": checkpoint["eta"].isoformat(),
                "wind_mph": (
                    None if assessment.wind.value is None
                    else float(assessment.wind.value)
                ),
                "rain_in_hr": (
                    None if assessment.rain.value is None
                    else float(assessment.rain.value)
                ),
                "snow_in_hr": (
                    None if assessment.snow.value is None
                    else float(assessment.snow.value)
                ),
                "final_severity": (
                    None if assessment.final_severity is None
                    else assessment.final_severity.name
                ),
                "is_complete": assessment.is_complete,
                "reason_codes": list(assessment.reason_codes),
            }
        )
    return serialized


def _metrics_dict(metrics: RouteRiskMetrics) -> dict:
    return {
        "total_distance_mi": str(metrics.total_distance_mi),
        "assessed_miles": str(metrics.assessed_miles),
        "unknown_miles": str(metrics.unknown_miles),
        "severe_miles": str(metrics.severe_miles),
        "high_miles": str(metrics.high_miles),
        "no_travel_miles": str(metrics.no_travel_miles),
        "average_risk": (
            None if metrics.average_risk is None
            else str(round(float(metrics.average_risk), 4))
        ),
    }
