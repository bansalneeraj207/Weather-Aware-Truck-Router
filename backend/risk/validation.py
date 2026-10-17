import math
from decimal import Decimal

Number = int | float | Decimal


class InvalidMeasurementError(ValueError):
    """Raised when a weather measurement or load is not usable."""


class InvalidRouteError(ValueError):
    """Raised when route data is invalid or internally inconsistent."""


def to_decimal(value: Number, *, field: str) -> Decimal:
    if isinstance(value, bool):
        raise InvalidMeasurementError(f"{field} must be a finite number, not bool")
    if isinstance(value, Decimal):
        if value.is_finite():
            return value
    elif isinstance(value, int):
        return Decimal(value)
    elif isinstance(value, float) and math.isfinite(value):
        return Decimal(str(value))
    raise InvalidMeasurementError(f"{field} must be a finite number")


def require_non_negative_measurement(value: Number, *, field: str) -> Decimal:
    value = to_decimal(value, field=field)
    if value < 0:
        raise InvalidMeasurementError(f"{field} must be >= 0, got {value!r}")
    return value


def require_positive_load(value: Number) -> Decimal:
    value = to_decimal(value, field="load_lb")
    if value <= 0:
        raise InvalidMeasurementError(f"load_lb must be > 0, got {value!r}")
    return value


def require_positive_route_value(value: Number, *, field: str) -> Decimal:
    value = to_decimal(value, field=field)
    if value <= 0:
        raise InvalidRouteError(f"{field} must be > 0, got {value!r}")
    return value


def require_non_negative_route_value(value: Number, *, field: str) -> Decimal:
    value = to_decimal(value, field=field)
    if value < 0:
        raise InvalidRouteError(f"{field} must be >= 0, got {value!r}")
    return value
