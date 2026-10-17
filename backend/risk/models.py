from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from .policy import Severity, WeatherCondition
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

