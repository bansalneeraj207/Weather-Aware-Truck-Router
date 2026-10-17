from decimal import Decimal

from .models import CheckpointRiskAssessment, ConditionAssessment
from .policy import ReasonCode, SEVERE_UP_TO, THRESHOLDS, Severity, WeatherCondition
from .validation import Number, require_non_negative_measurement, require_positive_load


def _severity(value: Number, condition: WeatherCondition) -> Severity:
    value = require_non_negative_measurement(value, field=f"{condition.value}_value")
    for boundary, severity in THRESHOLDS[condition]:
        if value < Decimal(boundary):
            return severity
    severe_limit, inclusive = SEVERE_UP_TO[condition]
    if value <= severe_limit if inclusive else value < severe_limit:
        return Severity.SEVERE
    return Severity.NO_TRAVEL


def classify_wind(wind_mph: Number) -> Severity:
    return _severity(wind_mph, WeatherCondition.WIND)


def classify_rain(rain_in_hr: Number) -> Severity:
    return _severity(rain_in_hr, WeatherCondition.RAIN)


def classify_snow(snow_in_hr: Number) -> Severity:
    return _severity(snow_in_hr, WeatherCondition.SNOW)


def _assessment(condition: WeatherCondition, value: Number | None) -> ConditionAssessment:
    if value is None:
        return ConditionAssessment(condition, None, None, (f"MISSING_{condition.name}",), (f"{condition.value.title()} is missing; severity is UNKNOWN.",))
    value = require_non_negative_measurement(value, field=f"{condition.value}_value")
    severity = _severity(value, condition)
    return ConditionAssessment(condition, severity, value, (f"{condition.name}_{severity.name}",), (f"{condition.value.title()} severity is {severity.name}.",))


def _wind_assessments(wind_mph: Number | None, load_lb: Number) -> tuple[ConditionAssessment, ConditionAssessment]:
    load = require_positive_load(load_lb)
    wind = _assessment(WeatherCondition.WIND, wind_mph)
    if wind.severity is None:
        return wind, ConditionAssessment(WeatherCondition.WIND, None, None, (ReasonCode.MISSING_WIND, ReasonCode.LOAD_WIND_NOT_APPLIED), ("Load-adjusted wind is UNKNOWN because wind is missing.",))

    speed = wind.value
    assert speed is not None
    severity, reason = wind.severity, ReasonCode.LOAD_WIND_UNCHANGED
    if speed >= 55:
        severity, reason = Severity.NO_TRAVEL, ReasonCode.LOAD_WIND_ANY_LOAD_NO_TRAVEL
    elif speed >= 45 and load > 30000:
        severity, reason = Severity.NO_TRAVEL, ReasonCode.LOAD_WIND_HEAVY_NO_TRAVEL
    elif speed >= 35 and load > 40000:
        severity, reason = Severity.SEVERE, ReasonCode.LOAD_WIND_UPGRADE_SEVERE
    return wind, ConditionAssessment(WeatherCondition.WIND, severity, speed, (f"WIND_{wind.severity.name}", reason), (f"Wind severity is {severity.name} after load adjustment.",))


def assess_checkpoint(*, wind_mph: Number | None, rain_in_hr: Number | None, snow_in_hr: Number | None, load_lb: Number) -> CheckpointRiskAssessment:
    """Classify one checkpoint. Missing weather leaves its final result unknown."""
    wind, adjusted_wind = _wind_assessments(wind_mph, load_lb)
    rain = _assessment(WeatherCondition.RAIN, rain_in_hr)
    snow = _assessment(WeatherCondition.SNOW, snow_in_hr)
    assessments = ((WeatherCondition.WIND, adjusted_wind), (WeatherCondition.RAIN, rain), (WeatherCondition.SNOW, snow))
    known = [(condition, assessment.severity) for condition, assessment in assessments if assessment.severity is not None]
    known_max = max((severity for _, severity in known), default=None)
    dominating = tuple(condition for condition, severity in known if severity == known_max)
    complete = len(known) == len(assessments)

    all_assessments = (wind, adjusted_wind, rain, snow)
    codes = list(dict.fromkeys(code for assessment in all_assessments for code in assessment.reason_codes))
    explanations = list(dict.fromkeys(text for assessment in all_assessments for text in assessment.explanations))
    if complete:
        assert known_max is not None
        codes.extend((ReasonCode.for_checkpoint(known_max), *(ReasonCode.dominated_by(condition) for condition in dominating)))
        explanations.append(f"Final checkpoint severity is {known_max.name}.")
    else:
        codes.append(ReasonCode.CHECKPOINT_INCOMPLETE)
        explanations.append("Checkpoint assessment is incomplete (UNKNOWN).")

    return CheckpointRiskAssessment(wind, adjusted_wind, rain, snow, known_max if complete else None, known_max, complete, dominating, tuple(codes), tuple(explanations))
