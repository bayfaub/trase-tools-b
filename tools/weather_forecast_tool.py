r"""WeatherForecast: US point forecast from the National Weather Service.

Wraps api.weather.gov, which is free, keyless and public. The API is a two-hop
lookup and this tool hides that: ``/points/{lat},{lon}`` resolves a coordinate
to a forecast office grid and returns the URL of the forecast for it, which is
then fetched. Doing it in one tool call keeps the model from having to chain two
opaque URL fetches.

NWS requires a descriptive ``User-Agent`` and returns 403 without one, so the
header is not optional decoration. Coverage is the United States and its
territories only: a coordinate outside it resolves to a 404 at the points hop,
which is reported as a clear message rather than a raw status code.

Serve locally with:

    trase-os-sdk run-tool tools/weather_forecast_tool.py
"""

from __future__ import annotations

from typing import Any, ClassVar

import httpx
from pydantic import BaseModel, Field
from trase_os_sdk.tools import BaseTool


_POINTS_URL = "https://api.weather.gov/points/{lat},{lon}"

# NWS asks callers to identify themselves with a contact. An anonymous or absent
# agent is rejected with 403, so this is part of the contract, not politeness.
_USER_AGENT = "trase-tools-b-weather-tool (support@trase.ai)"

_TIMEOUT_SECONDS = 20.0
_MAX_PERIODS = 14


class WeatherForecastInputs(BaseModel):
    """Parameters for a single point-forecast lookup."""

    latitude: float = Field(description="Latitude in decimal degrees, e.g. 38.8894.")
    longitude: float = Field(
        description="Longitude in decimal degrees, negative for the western hemisphere, e.g. -77.0352."
    )
    periods: int = Field(
        default=1,
        description=(
            "How many forecast periods to return, starting with the current one. "
            "A period is roughly half a day ('Tonight', 'Tuesday'). 1-14."
        ),
    )


class ForecastPeriod(BaseModel):
    """One NWS forecast period."""

    name: str = Field(description="Period label, e.g. 'Tonight' or 'Tuesday'.")
    start_time: str = Field(description="ISO 8601 start time of the period.")
    is_daytime: bool = Field(description="True for a daytime period.")
    temperature: int = Field(description="Forecast temperature.")
    temperature_unit: str = Field(description="Unit of the temperature, 'F' or 'C'.")
    wind_speed: str = Field(description="Wind speed as reported, e.g. '5 mph'.")
    wind_direction: str = Field(description="Wind direction as reported, e.g. 'SW'.")
    short_forecast: str = Field(description="One-line summary, e.g. 'Partly Cloudy'.")
    detailed_forecast: str = Field(description="Full prose forecast for the period.")


class WeatherForecastResult(BaseModel):
    """Structured forecast for one coordinate."""

    location: str = Field(description="Nearest named place, e.g. 'Linn, KS'.")
    forecast_office: str = Field(description="NWS grid id, e.g. 'TOP 32,81'.")
    periods: list[ForecastPeriod] = Field(description="Requested forecast periods, in order.")
    summary: str = Field(description="Human-readable summary of the first period.")


def _get_json(client: httpx.Client, url: str, *, what: str) -> dict[str, Any]:
    """GET ``url`` and return parsed JSON, mapping failures to clear messages."""
    try:
        response = client.get(url)
    except httpx.HTTPError as exc:
        raise ValueError(f"could not reach the National Weather Service for {what}: {exc}") from exc

    if response.status_code == 404:
        raise ValueError(
            f"the National Weather Service has no {what} for that coordinate; "
            "api.weather.gov covers the United States and its territories only"
        )
    if response.status_code >= 400:
        raise ValueError(
            f"National Weather Service returned {response.status_code} for {what}: "
            f"{response.text[:200]}"
        )
    return response.json()


class WeatherForecast(BaseTool):
    """Look up the National Weather Service forecast for a US coordinate."""

    name: ClassVar[str] = "WeatherForecast"
    description: ClassVar[str] = (
        "Get the National Weather Service forecast for a latitude/longitude in the "
        "United States. Returns temperature, wind and a prose forecast for one or "
        "more periods. US coverage only; returns a WeatherForecastResult JSON object."
    )
    pydantic_inputs: ClassVar[type[BaseModel]] = WeatherForecastInputs
    output_type: ClassVar[str] = "object"
    output_schema: ClassVar[dict] = WeatherForecastResult.model_json_schema()

    def forward(
        self, latitude: float, longitude: float, periods: int = 1
    ) -> WeatherForecastResult:
        """Resolve the coordinate to a grid, then fetch and shape its forecast."""
        if not -90.0 <= latitude <= 90.0:
            raise ValueError(f"latitude must be between -90 and 90; got {latitude}")
        if not -180.0 <= longitude <= 180.0:
            raise ValueError(f"longitude must be between -180 and 180; got {longitude}")
        wanted = max(1, min(int(periods), _MAX_PERIODS))

        headers = {"User-Agent": _USER_AGENT, "Accept": "application/geo+json"}
        with httpx.Client(timeout=_TIMEOUT_SECONDS, headers=headers, follow_redirects=True) as client:
            point = _get_json(
                client,
                _POINTS_URL.format(lat=latitude, lon=longitude),
                what="grid point",
            )["properties"]

            forecast_url = point.get("forecast")
            if not forecast_url:
                raise ValueError("the grid point carried no forecast URL; nothing to fetch")

            raw_periods = _get_json(client, forecast_url, what="forecast")["properties"]["periods"]

        place = point.get("relativeLocation", {}).get("properties", {})
        location = ", ".join(p for p in (place.get("city"), place.get("state")) if p) or "unknown"
        office = f"{point.get('gridId', '?')} {point.get('gridX', '?')},{point.get('gridY', '?')}"

        shaped = [
            ForecastPeriod(
                name=p.get("name", ""),
                start_time=p.get("startTime", ""),
                is_daytime=bool(p.get("isDaytime", False)),
                temperature=int(p.get("temperature", 0)),
                temperature_unit=p.get("temperatureUnit", ""),
                wind_speed=p.get("windSpeed", ""),
                wind_direction=p.get("windDirection", ""),
                short_forecast=p.get("shortForecast", ""),
                detailed_forecast=p.get("detailedForecast", ""),
            )
            for p in raw_periods[:wanted]
        ]
        if not shaped:
            raise ValueError("the National Weather Service returned no forecast periods")

        first = shaped[0]
        return WeatherForecastResult(
            location=location,
            forecast_office=office,
            periods=shaped,
            summary=(
                f"{location} — {first.name}: {first.short_forecast}, "
                f"{first.temperature}°{first.temperature_unit}, "
                f"wind {first.wind_speed} {first.wind_direction}"
            ),
        )
