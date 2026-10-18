"""Transit proximity data - safer near transit stops/stations.

Sources:
- TransitLand API (requires API key now): https://transit.land/
- GTFS feeds from local agencies
- OpenMobilityData

Get your free key at: https://transit.land/documentation/#api-keys

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
class TransitProximity:
    """Normalized transit proximity: 1.0 = very close to transit, 0.0 = far."""

    score: float = 0.5
    source: str = "transitland"
    nearest_stop_distance_m: float | None = None
    stop_count_500m: int = 0


@dataclass(slots=True)
class TransitConditions:
    """Fallback transit conditions when provider unavailable."""

    score: float = 0.5
    source: str = "default"
    nearest_stop_distance_m: float | None = None
    stop_count_500m: int = 0


class TransitProvider(ABC):
    @abstractmethod
    async def get_proximity(self, location: Coordinate, at_time: datetime) -> TransitProximity: ...


class TransitLandProvider(TransitProvider):
    """Fetch transit stops from TransitLand API (requires API key)."""

    BASE_URL = "https://transit.land/api/v2/rest"

    def __init__(self, settings: Settings | None = None, client: httpx.AsyncClient | None = None):
        self.settings = settings or get_settings()
        self.api_key = settings.transit_api_key
        self.client = client or httpx.AsyncClient(timeout=self.settings.http_timeout_seconds)

    async def get_proximity(self, location: Coordinate, at_time: datetime) -> TransitProximity:
        if not self.api_key:
            # No API key configured - return neutral
            return TransitProximity(0.5, "transitland", None, 0)

        try:
            # Search for stops near location
            params = {
                "lat": location.lat,
                "lon": location.lon,
                "r": 1000,  # 1km radius
                "per_page": 50,
                "apikey": self.api_key,
            }
            data = await get_json(
                self.client,
                f"{self.BASE_URL}/stops",
                params=params,
                retries=self.settings.http_max_retries,
            )

            stops = data.get("stops", [])
            if not stops:
                return TransitProximity(0.1, "transitland", None, 0)

            # Calculate distances
            from app.routing.geometry import haversine_m

            distances = []
            for stop in stops:
                stop_lat = stop.get("lat")
                stop_lon = stop.get("lon")
                if stop_lat and stop_lon:
                    d = haversine_m(location, Coordinate(lat=stop_lat, lon=stop_lon))
                    distances.append(d)

            if not distances:
                return TransitProximity(0.1, "transitland", None, 0)

            min_dist = min(distances)
            count_500m = sum(1 for d in distances if d <= 500)

            # Score: closer = safer (more people, better lighting, more eyes)
            if min_dist <= 100:
                score = 1.0
            elif min_dist <= 300:
                score = 0.8
            elif min_dist <= 500:
                score = 0.6
            elif min_dist <= 1000:
                score = 0.4
            else:
                score = 0.2

            return TransitProximity(score, "transitland", min_dist, count_500m)

        except (UpstreamServiceError, httpx.HTTPError, ValueError, KeyError):
            # Transit.land API error - return neutral
            return TransitProximity(0.5, "transitland", None, 0)


class NullTransitProvider(TransitProvider):
    async def get_proximity(self, location: Coordinate, at_time: datetime) -> TransitProximity:
        return TransitProximity()


def create_transit_provider(settings: Settings | None = None) -> TransitProvider:
    settings = settings or get_settings()
    return TransitLandProvider(settings)
