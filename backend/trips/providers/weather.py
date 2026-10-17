"""Hourly forecast weather for checkpoints via Open-Meteo (no API key).

Wind is the 10 m speed. Rain and snowfall are that hour's totals, which match
the risk engine's hourly rates. Points are requested in batches of 100.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from trips.providers.errors import ProviderError
from trips.providers.http import request_with_retry

OPEN_METEO_BASE_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_BATCH_SIZE = 100
OPEN_METEO_FORECAST_DAYS = 16
_MATCH_WINDOW = 3600


class WeatherReading:
    """One hour's weather. Missing values stay None (UNKNOWN downstream)."""

    def __init__(
        self,
        wind_mph: float | None,
        rain_in_hr: float | None,
        snow_in_hr: float | None,
    ) -> None:
        self.wind_mph = wind_mph
        self.rain_in_hr = rain_in_hr
        self.snow_in_hr = snow_in_hr


class HourlyForecast:
    """Hourly wind, rain, and snow for one coordinate."""

    def __init__(
        self,
        times: list[datetime],
        wind_mph: list[float | None],
        rain_in_hr: list[float | None],
        snow_in_hr: list[float | None],
    ) -> None:
        self.times = times
        self.wind_mph = wind_mph
        self.rain_in_hr = rain_in_hr
        self.snow_in_hr = snow_in_hr

    def at(self, moment: datetime) -> WeatherReading:
        """Reading for the forecast hour nearest ``moment``.

        A moment more than an hour from every returned hour is missing, not zero.
        """
        if not self.times:
            return WeatherReading(None, None, None)
        target = moment.astimezone(timezone.utc)
        index = min(
            range(len(self.times)),
            key=lambda position: abs((self.times[position] - target).total_seconds()),
        )
        if abs((self.times[index] - target).total_seconds()) > _MATCH_WINDOW:
            return WeatherReading(None, None, None)
        return WeatherReading(
            self.wind_mph[index],
            self.rain_in_hr[index],
            self.snow_in_hr[index],
        )


def fetch_hourly_forecast(
    points: list[tuple[float, float]],
    start: datetime,
    end: datetime,
) -> list[HourlyForecast]:
    """Forecast for each (lat, lon), covering ``start`` through ``end`` in UTC."""
    if not points:
        return []
    if end < start:
        raise ProviderError("Forecast window ends before it starts.")

    forecasts: list[HourlyForecast] = []
    for offset in range(0, len(points), OPEN_METEO_BATCH_SIZE):
        forecasts.extend(
            _fetch_batch(points[offset : offset + OPEN_METEO_BATCH_SIZE], start, end)
        )
    return forecasts


def _fetch_batch(
    points: list[tuple[float, float]],
    start: datetime,
    end: datetime,
) -> list[HourlyForecast]:
    params = {
        "latitude": ",".join(f"{lat}" for lat, _ in points),
        "longitude": ",".join(f"{lon}" for _, lon in points),
        "hourly": "wind_speed_10m,rain,snowfall",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "timezone": "UTC",
        "start_date": start.astimezone(timezone.utc).date().isoformat(),
        "end_date": end.astimezone(timezone.utc).date().isoformat(),
    }
    url = f"{OPEN_METEO_BASE_URL}?{urllib.parse.urlencode(params)}"
    def request_forecast() -> dict | list[dict]:
        request = urllib.request.Request(url)
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))

    try:
        data = request_with_retry(request_forecast, service_name="Weather service")
    except urllib.error.HTTPError as exc:
        raise ProviderError(f"Weather service could not complete this request ({exc.code}).") from exc
    except ValueError as exc:
        raise ProviderError(f"Weather service returned invalid JSON: {exc}") from exc

    entries = data if isinstance(data, list) else [data]
    if len(entries) != len(points):
        raise ProviderError("Weather service returned an unexpected number of forecasts.")
    return [_forecast_from_entry(entry) for entry in entries]


def _forecast_from_entry(entry: dict) -> HourlyForecast:
    hourly = entry.get("hourly") or {}
    units = entry.get("hourly_units") or {}
    times = [_parse_time(value) for value in hourly.get("time") or []]
    wind = [_as_float(value) for value in hourly.get("wind_speed_10m") or []]
    rain = [_as_float(value) for value in hourly.get("rain") or []]
    snow = [
        _snow_inches(value, units.get("snowfall"))
        for value in hourly.get("snowfall") or []
    ]
    count = min(len(times), len(wind), len(rain), len(snow))
    return HourlyForecast(times[:count], wind[:count], rain[:count], snow[:count])


def _parse_time(value: object) -> datetime:
    if not isinstance(value, str):
        raise ProviderError("Weather service returned an unreadable forecast time.")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _as_float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _snow_inches(value: object, unit: object) -> float | None:
    amount = _as_float(value)
    if amount is None:
        return None
    if isinstance(unit, str) and "cm" in unit.lower():
        return amount / 2.54
    return amount
