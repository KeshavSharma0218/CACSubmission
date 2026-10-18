"""Optional weather contract with a free US National Weather Service adapter."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

import httpx

from app.database.schemas import Coordinate
from app.utils.config import Settings, get_settings
from app.utils.http_client import UpstreamServiceError, get_json


@dataclass(slots=True)
class WeatherConditions:
    severity: float = 0.0
    description: str = "neutral"


class WeatherProvider(ABC):
    @abstractmethod
    async def get_conditions(
        self, location: Coordinate, at_time: datetime
    ) -> WeatherConditions: ...


class NeutralWeatherProvider(WeatherProvider):
    async def get_conditions(self, location: Coordinate, at_time: datetime) -> WeatherConditions:
        return WeatherConditions()


class NWSWeatherProvider(WeatherProvider):
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self.client = client or httpx.AsyncClient(
            timeout=settings.http_timeout_seconds,
            headers={"User-Agent": settings.nominatim_user_agent},
            follow_redirects=True,  # Follow 301 redirects from weather.gov
        )

    async def get_conditions(self, location: Coordinate, at_time: datetime) -> WeatherConditions:
        try:
            # NWS points API may return redirects - follow them
            point = await get_json(
                self.client,
                f"https://api.weather.gov/points/{location.lat},{location.lon}",
                retries=self.settings.http_max_retries,
            )
            forecast_url = point["properties"]["forecastHourly"]
            forecast = await get_json(
                self.client,
                forecast_url,
                retries=self.settings.http_max_retries,
            )
            text = forecast["properties"]["periods"][0].get("shortForecast", "")
            severe = any(word in text.lower() for word in ("storm", "snow", "ice", "heavy rain"))
            return WeatherConditions(0.5 if severe else 0.0, text or "neutral")
        except (UpstreamServiceError, httpx.HTTPError, ValueError, KeyError):
            # Weather is optional - return neutral if unavailable
            return WeatherConditions()


def create_weather_provider(settings: Settings | None = None) -> WeatherProvider:
    settings = settings or get_settings()
    return (
        NWSWeatherProvider(settings)
        if settings.weather_provider == "nws"
        else NeutralWeatherProvider()
    )
