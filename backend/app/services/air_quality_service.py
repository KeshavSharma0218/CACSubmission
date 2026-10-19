"""Air quality data from OpenAQ v3 API (requires API key).

OpenAQ v2 is deprecated (returns 410 Gone). v3 requires an API key.
Get your free key at: https://docs.openaq.org/

Falls back to neutral conditions when API is unavailable or key is missing.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

import httpx

from app.database.schemas import Coordinate
from app.utils.config import Settings, get_settings
from app.utils.http_client import UpstreamServiceError, get_json


@dataclass(slots=True)
class AirQualityConditions:
    """Normalized air quality: 0.0 = hazardous, 1.0 = good."""

    aqi: float = 50.0  # US AQI 0-500, normalized to 0-1
    source: str = "openaq"
    description: str = "moderate"
    pollutant: str | None = None


class AirQualityProvider(ABC):
    @abstractmethod
    async def get_conditions(
        self, location: Coordinate, at_time: datetime
    ) -> AirQualityConditions: ...


class OpenAQProvider(AirQualityProvider):
    """Fetch air quality from OpenAQ v3 API (requires API key)."""

    BASE_URL = "https://api.openaq.org/v3"

    def __init__(self, settings: Settings | None = None, client: httpx.AsyncClient | None = None):
        self.settings = settings or get_settings()
        self.api_key = settings.air_quality_api_key
        self.client = client or httpx.AsyncClient(timeout=self.settings.http_timeout_seconds)

    async def get_conditions(self, location: Coordinate, at_time: datetime) -> AirQualityConditions:
        if not self.api_key:
            # No API key configured - return neutral
            return AirQualityConditions(0.5, "openaq", "no api key")

        try:
            headers = {"X-API-Key": self.api_key}

            # Find nearest measurement location - v3 API
            params = {
                "coordinates": f"{location.lat},{location.lon}",
                "radius": 10000,  # 10km in meters
                "limit": 1,
            }
            data = await get_json(
                self.client,
                f"{self.BASE_URL}/locations",
                params=params,
                headers=headers,
                retries=self.settings.http_max_retries,
            )

            results = data.get("results", [])
            if not results:
                return AirQualityConditions(0.7, "openaq", "no nearby station")

            location_id = results[0]["id"]

            # Get latest measurements - v3 uses /v3/locations/{id}/latest
            meas_data = await get_json(
                self.client,
                f"{self.BASE_URL}/locations/{location_id}/latest",
                headers=headers,
                retries=self.settings.http_max_retries,
            )

            measurements = meas_data.get("results", [])
            if not measurements:
                return AirQualityConditions(0.7, "openaq", "no recent measurements")

            # Calculate US AQI from PM2.5 if available
            pm25 = None
            for meas in measurements:
                if meas.get("parameter") == "pm25":
                    pm25 = meas.get("value")
                    break

            if pm25 is not None:
                aqi = self._pm25_to_aqi(pm25)
                normalized = max(0.0, 1.0 - aqi / 500.0)
                return AirQualityConditions(
                    normalized,
                    "openaq",
                    "good" if aqi <= 50 else "moderate" if aqi <= 100 else "unhealthy",
                    "pm25",
                )

            return AirQualityConditions(0.7, "openaq", "no pm25 data")

        except (UpstreamServiceError, httpx.HTTPError, ValueError, KeyError):
            # OpenAQ API error - return neutral
            return AirQualityConditions(0.5, "openaq", "service unavailable")

    @staticmethod
    def _pm25_to_aqi(pm25: float) -> float:
        """Convert PM2.5 μg/m³ to US AQI (simplified)."""
        breakpoints = [
            (0.0, 12.0, 0, 50),
            (12.1, 35.4, 51, 100),
            (35.5, 55.4, 101, 150),
            (55.5, 150.4, 151, 200),
            (150.5, 250.4, 201, 300),
            (250.5, 350.4, 301, 400),
            (350.5, 500.4, 401, 500),
        ]
        for c_low, c_high, aqi_low, aqi_high in breakpoints:
            if c_low <= pm25 <= c_high:
                return aqi_low + (aqi_high - aqi_low) * (pm25 - c_low) / (c_high - c_low)
        return 500.0


class NullAirQualityProvider(AirQualityProvider):
    async def get_conditions(self, location: Coordinate, at_time: datetime) -> AirQualityConditions:
        return AirQualityConditions()


def create_air_quality_provider(settings: Settings | None = None) -> AirQualityProvider:
    settings = settings or get_settings()
    if settings.air_quality_provider == "openaq":
        return OpenAQProvider(settings)
    return NullAirQualityProvider()
