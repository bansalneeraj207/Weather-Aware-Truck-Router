from decimal import Decimal
from enum import IntEnum, StrEnum


class Severity(IntEnum):
    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4


class WeatherCondition(StrEnum):
    WIND = "wind"
    RAIN = "rain"
    SNOW = "snow"


class RecommendationStatus(StrEnum):
    RECOMMENDED = "RECOMMENDED"
    NO_ACCEPTABLE_ROUTE = "NO_ACCEPTABLE_ROUTE"
    NO_ROUTES = "NO_ROUTES"


THRESHOLDS = {
    WeatherCondition.WIND: (("25", Severity.LOW), ("35", Severity.MODERATE), ("45", Severity.HIGH)),
    WeatherCondition.RAIN: (("0.10", Severity.LOW), ("0.25", Severity.MODERATE), ("0.50", Severity.HIGH)),
    WeatherCondition.SNOW: (("0.5", Severity.LOW), ("1.0", Severity.MODERATE), ("2.0", Severity.HIGH)),
}
SEVERE_UP_TO = {
    WeatherCondition.WIND: (Decimal("55"), False),
    WeatherCondition.RAIN: (Decimal("1.00"), True),
    WeatherCondition.SNOW: (Decimal("3.0"), True),
}


class ReasonCode(StrEnum):
    WIND_LOW = "WIND_LOW"
    WIND_MODERATE = "WIND_MODERATE"
    WIND_HIGH = "WIND_HIGH"
    WIND_SEVERE = "WIND_SEVERE"
    WIND_NO_TRAVEL = "WIND_NO_TRAVEL"
    RAIN_LOW = "RAIN_LOW"
    RAIN_MODERATE = "RAIN_MODERATE"
    RAIN_HIGH = "RAIN_HIGH"
    RAIN_SEVERE = "RAIN_SEVERE"
    RAIN_NO_TRAVEL = "RAIN_NO_TRAVEL"
    SNOW_LOW = "SNOW_LOW"
    SNOW_MODERATE = "SNOW_MODERATE"
    SNOW_HIGH = "SNOW_HIGH"
    SNOW_SEVERE = "SNOW_SEVERE"
    SNOW_NO_TRAVEL = "SNOW_NO_TRAVEL"
    LOAD_WIND_ANY_LOAD_NO_TRAVEL = "LOAD_WIND_ANY_LOAD_NO_TRAVEL"
    LOAD_WIND_HEAVY_NO_TRAVEL = "LOAD_WIND_HEAVY_NO_TRAVEL"
    LOAD_WIND_UPGRADE_SEVERE = "LOAD_WIND_UPGRADE_SEVERE"
    LOAD_WIND_UNCHANGED = "LOAD_WIND_UNCHANGED"
    LOAD_WIND_NOT_APPLIED = "LOAD_WIND_NOT_APPLIED"
    MISSING_WIND = "MISSING_WIND"
    MISSING_RAIN = "MISSING_RAIN"
    MISSING_SNOW = "MISSING_SNOW"
    CHECKPOINT_LOW = "CHECKPOINT_LOW"
    CHECKPOINT_MODERATE = "CHECKPOINT_MODERATE"
    CHECKPOINT_HIGH = "CHECKPOINT_HIGH"
    CHECKPOINT_SEVERE = "CHECKPOINT_SEVERE"
    CHECKPOINT_NO_TRAVEL = "CHECKPOINT_NO_TRAVEL"
    CHECKPOINT_INCOMPLETE = "CHECKPOINT_INCOMPLETE"
    DOMINATED_BY_WIND = "DOMINATED_BY_WIND"
    DOMINATED_BY_RAIN = "DOMINATED_BY_RAIN"
    DOMINATED_BY_SNOW = "DOMINATED_BY_SNOW"

    @classmethod
    def for_wind(cls, severity: Severity) -> "ReasonCode":
        return cls(f"WIND_{severity.name}")

    @classmethod
    def for_rain(cls, severity: Severity) -> "ReasonCode":
        return cls(f"RAIN_{severity.name}")

    @classmethod
    def for_snow(cls, severity: Severity) -> "ReasonCode":
        return cls(f"SNOW_{severity.name}")

    @classmethod
    def for_checkpoint(cls, severity: Severity) -> "ReasonCode":
        return cls(f"CHECKPOINT_{severity.name}")

    @classmethod
    def dominated_by(cls, condition: WeatherCondition) -> "ReasonCode":
        return cls(f"DOMINATED_BY_{condition.name}")


class RecommendationReasonCode(StrEnum):
    RECOMMENDATION_RECOMMENDED = "RECOMMENDATION_RECOMMENDED"
    RECOMMENDATION_NO_ACCEPTABLE_ROUTE = "RECOMMENDATION_NO_ACCEPTABLE_ROUTE"
    RECOMMENDATION_NO_ROUTES = "RECOMMENDATION_NO_ROUTES"
    RECOMMENDATION_ALL_ROUTES_NO_TRAVEL = "RECOMMENDATION_ALL_ROUTES_NO_TRAVEL"
    ROUTE_NO_TRAVEL_EXPOSURE = "ROUTE_NO_TRAVEL_EXPOSURE"
    ROUTE_INCOMPLETE_COVERAGE = "ROUTE_INCOMPLETE_COVERAGE"
    ROUTE_FULLY_ASSESSED = "ROUTE_FULLY_ASSESSED"
    ROUTE_RECOMMENDED_INCOMPLETE = "ROUTE_RECOMMENDED_INCOMPLETE"
