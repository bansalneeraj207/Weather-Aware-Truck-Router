from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from .policy import RecommendationStatus, Severity, WeatherCondition
from .validation import InvalidRouteError, Number, require_non_negative_route_value, require_positive_route_value

DISTANCE_SUM_TOLERANCE_MI = Decimal("0.001")


@dataclass(frozen=True, slots=True)
class ConditionAssessment:
    condition: WeatherCondition
    severity: Severity | None
    value: Decimal | None
    reason_codes: tuple[str, ...]
    explanations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CheckpointRiskAssessment:
    wind: ConditionAssessment
    load_adjusted_wind: ConditionAssessment
    rain: ConditionAssessment
    snow: ConditionAssessment
    final_severity: Severity | None
    known_max_severity: Severity | None
    is_complete: bool
    dominating_conditions: tuple[WeatherCondition, ...]
    reason_codes: tuple[str, ...]
    explanations: tuple[str, ...]

    @property
    def wind_severity(self) -> Severity | None: return self.wind.severity

    @property
    def rain_severity(self) -> Severity | None: return self.rain.severity

    @property
    def snow_severity(self) -> Severity | None: return self.snow.severity

    @property
    def load_adjusted_wind_severity(self) -> Severity | None: return self.load_adjusted_wind.severity


@dataclass(frozen=True, slots=True)
class RouteSegmentSpec:
    length_mi: Number
    assessment: CheckpointRiskAssessment


@dataclass(frozen=True, slots=True)
class RouteSegment:
    index: int
    start_mi: Decimal
    end_mi: Decimal
    length_mi: Decimal
    assessment: CheckpointRiskAssessment

    @property
    def checkpoint_mi(self) -> Decimal: return self.start_mi


@dataclass(frozen=True, slots=True)
class Route:
    route_id: str
    distance_mi: Decimal
    travel_time_hr: Decimal
    segments: tuple[RouteSegment, ...]

    @property
    def segment_count(self) -> int: return len(self.segments)

    @classmethod
    def build(cls, *, route_id: str, distance_mi: Number, travel_time_hr: Number,
              segments: Sequence[RouteSegmentSpec], distance_tolerance_mi: Number | None = None) -> "Route":
        if not isinstance(route_id, str) or not route_id.strip():
            raise InvalidRouteError(f"route_id must be a non-empty string, got {route_id!r}")
        distance = require_positive_route_value(distance_mi, field="distance_mi")
        travel_time = require_positive_route_value(travel_time_hr, field="travel_time_hr")
        tolerance = DISTANCE_SUM_TOLERANCE_MI if distance_tolerance_mi is None else require_non_negative_route_value(distance_tolerance_mi, field="distance_tolerance_mi")
        specs = tuple(segments)
        if not specs:
            raise InvalidRouteError("a route requires at least one segment")

        resolved, position = [], Decimal(0)
        for index, spec in enumerate(specs):
            if not isinstance(spec, RouteSegmentSpec):
                raise InvalidRouteError(f"segments[{index}] must be a RouteSegmentSpec, got {type(spec).__name__}")
            if not isinstance(spec.assessment, CheckpointRiskAssessment):
                raise InvalidRouteError(f"segments[{index}].assessment must be a CheckpointRiskAssessment, got {type(spec.assessment).__name__}")
            length = require_positive_route_value(spec.length_mi, field=f"segments[{index}].length_mi")
            resolved.append(RouteSegment(index, position, position + length, length, spec.assessment))
            position += length

        if abs(position - distance) > tolerance:
            raise InvalidRouteError(f"segment lengths sum to {position} mi but route distance is {distance} mi (tolerance {tolerance} mi)")
        return cls(route_id, distance, travel_time, tuple(resolved))


@dataclass(frozen=True, slots=True)
class RouteRiskMetrics:
    total_distance_mi: Decimal
    assessed_miles: Decimal
    unknown_miles: Decimal
    severe_miles: Decimal
    high_miles: Decimal
    no_travel_miles: Decimal
    average_risk: Decimal | None

    @property
    def is_fully_assessed(self) -> bool: return self.unknown_miles == 0

    @property
    def has_no_travel_exposure(self) -> bool: return self.no_travel_miles > 0

    @property
    def low_or_moderate_miles(self) -> Decimal:
        return self.assessed_miles - self.severe_miles - self.high_miles - self.no_travel_miles


@dataclass(frozen=True, slots=True)
class RankedRoute:
    rank: int
    route: Route
    metrics: RouteRiskMetrics
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IneligibleRoute:
    route: Route
    metrics: RouteRiskMetrics
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RouteRecommendationResult:
    status: RecommendationStatus
    recommended_route: Route | None
    ranked_routes: tuple[RankedRoute, ...]
    ineligible_routes: tuple[IneligibleRoute, ...]
    reason_codes: tuple[str, ...]
    explanations: tuple[str, ...]
