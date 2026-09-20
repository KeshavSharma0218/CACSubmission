"""Traffic volume data from OSM tags and public APIs.

Sources:
- OSM maxspeed, lanes, highway type tags (free, no key)
- Could extend with Mapbox/TomTom/HERE traffic APIs (require keys)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from app.database.schemas import Coordinate
from app.utils.config import Settings, get_settings


@dataclass(slots=True)
class TrafficConditions:
    """Normalized traffic level: 0.0 = no traffic, 1.0 = heavy congestion."""

    level: float = 0.0
    source: str = "osm"
    description: str = "unknown"


class TrafficProvider(ABC):
    @abstractmethod
    async def get_conditions(
        self, location: Coordinate, at_time: datetime
    ) -> TrafficConditions: ...


class OSMTrafficProvider(TrafficProvider):
    """Estimate traffic from OSM road attributes (maxspeed, lanes, highway type)."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    async def get_conditions(self, location: Coordinate, at_time: datetime) -> TrafficConditions:
        # This would ideally query Overpass for nearby ways and their tags
        # For now, return a neutral estimate based on time of day
        hour = at_time.hour
        if 7 <= hour <= 9 or 16 <= hour <= 18:
            return TrafficConditions(0.6, "osm_time", "rush hour estimate")
        elif 22 <= hour or hour <= 5:
            return TrafficConditions(0.1, "osm_time", "low traffic night")
        return TrafficConditions(0.3, "osm_time", "moderate traffic")


class NullTrafficProvider(TrafficProvider):
    async def get_conditions(self, location: Coordinate, at_time: datetime) -> TrafficConditions:
        return TrafficConditions()


def create_traffic_provider(settings: Settings | None = None) -> TrafficProvider:
    settings = settings or get_settings()
    # Could add config for external traffic APIs here
    return OSMTrafficProvider(settings)
