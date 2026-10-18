from decimal import Decimal
from typing import Sequence

from .models import (
    IneligibleRoute,
    RankedRoute,
    Route,
    RouteRecommendationResult,
    RouteRiskMetrics,
    RouteSegmentSpec,
)
from .policy import RecommendationReasonCode, RecommendationStatus, Severity
from .validation import InvalidRouteError


def compute_route_metrics(route: Route) -> RouteRiskMetrics:
    miles = {severity: Decimal(0) for severity in Severity}
    unknown = weighted = Decimal(0)
    for segment in route.segments:
        severity = segment.assessment.final_severity
        if severity is None:
            unknown += segment.length_mi
        else:
            miles[severity] += segment.length_mi
            weighted += segment.length_mi * severity
    assessed = route.distance_mi - unknown
    return RouteRiskMetrics(route.distance_mi, assessed, unknown, miles[Severity.SEVERE], miles[Severity.HIGH], miles[Severity.NO_TRAVEL], weighted / assessed if assessed else None)


def recommend_routes(routes: Sequence[Route]) -> RouteRecommendationResult:
    routes = tuple(routes)
    if len({route.route_id for route in routes}) != len(routes):
        raise InvalidRouteError("duplicate route_id")
    if not routes:
        return RouteRecommendationResult(RecommendationStatus.NO_ROUTES, None, (), (), (RecommendationReasonCode.RECOMMENDATION_NO_ROUTES,), ("No route alternatives were supplied.",))

    measured = [(route, compute_route_metrics(route)) for route in routes]
    eligible = [(route, metrics) for route, metrics in measured if not metrics.has_no_travel_exposure]
    rejected = tuple(IneligibleRoute(route, metrics, (RecommendationReasonCode.ROUTE_NO_TRAVEL_EXPOSURE,)) for route, metrics in measured if metrics.has_no_travel_exposure)
    if not eligible:
        return RouteRecommendationResult(RecommendationStatus.NO_ACCEPTABLE_ROUTE, None, (), rejected, (RecommendationReasonCode.RECOMMENDATION_NO_ACCEPTABLE_ROUTE,), ("Every route has known No Travel exposure.",))

    infinity = Decimal("Infinity")
    ordered = sorted(eligible, key=lambda item: (not item[1].is_fully_assessed, item[1].severe_miles, item[1].high_miles, item[1].average_risk if item[1].average_risk is not None else infinity, item[1].unknown_miles, item[0].travel_time_hr, item[0].route_id))
    ranked = tuple(
        RankedRoute(rank, route, metrics, tuple(code for code in (
            RecommendationReasonCode.RECOMMENDATION_RECOMMENDED if rank == 1 else None,
            RecommendationReasonCode.ROUTE_FULLY_ASSESSED if metrics.is_fully_assessed else RecommendationReasonCode.ROUTE_INCOMPLETE_COVERAGE,
            RecommendationReasonCode.ROUTE_RECOMMENDED_INCOMPLETE if rank == 1 and not metrics.is_fully_assessed else None,
        ) if code is not None))
        for rank, (route, metrics) in enumerate(ordered, 1)
    )
    best, metrics = ordered[0]
    codes = [RecommendationReasonCode.RECOMMENDATION_RECOMMENDED]
    if not metrics.is_fully_assessed:
        codes.append(RecommendationReasonCode.ROUTE_RECOMMENDED_INCOMPLETE)
    return RouteRecommendationResult(RecommendationStatus.RECOMMENDED, best, ranked, rejected, tuple(codes), ("Lowest weather-risk route selected.",))
