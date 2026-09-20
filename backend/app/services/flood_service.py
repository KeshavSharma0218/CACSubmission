"""Flood zone data from FEMA National Flood Hazard Layer (NFHL).

Sources:
- FEMA NFHL WMS/REST API (free)
- FEMA Flood Map Service Center
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

import httpx

from app.database.schemas import Coordinate
from app.utils.config import Settings, get_settings
from app.utils.http_client import get_json


@dataclass(slots=True)
class FloodConditions:
    """Normalized flood risk: 1.0 = no flood risk, 0.0 = high risk."""

    score: float = 1.0
    source: str = "fema"
    zone: str | None = None
    in_floodplain: bool = False


class FloodProvider(ABC):
    @abstractmethod
    async def get_conditions(self, location: Coordinate, at_time: datetime) -> FloodConditions: ...


class FEMANFHLProvider(FloodProvider):
    """Query FEMA NFHL for flood zone at a coordinate."""

    # FEMA NFHL REST endpoint
    BASE_URL = "https://hazards.fema.gov/gis/nfhl/rest/services/public/NFHL/MapServer"

    def __init__(self, settings: Settings | None = None, client: httpx.AsyncClient | None = None):
        self.settings = settings or get_settings()
        self.client = client or httpx.AsyncClient(timeout=self.settings.http_timeout_seconds)

    async def get_conditions(self, location: Coordinate, at_time: datetime) -> FloodConditions:
        try:
            # Query NFHL Identify endpoint for flood zone at point
            params = {
                "geometry": f"{location.lon},{location.lat}",
                "geometryType": "esriGeometryPoint",
                "sr": 4326,
                "layers": "all",
                "tolerance": 10,
                "mapExtent": f"{location.lon - 0.01},{location.lat - 0.01},{location.lon + 0.01},{location.lat + 0.01}",
                "imageDisplay": "400,400,96",
                "returnGeometry": "false",
                "f": "json",
            }

            data = await get_json(
                self.client,
                f"{self.BASE_URL}/identify",
                params=params,
                retries=self.settings.http_max_retries,
            )

            results = data.get("results", [])
            if not results:
                return FloodConditions(1.0, "fema", "no data", False)

            # Check for flood hazard layers
            flood_zones = []
            for result in results:
                layer_name = result.get("layerName", "").lower()
                if "flood" in layer_name or "sfha" in layer_name or "zone" in layer_name:
                    attrs = result.get("attributes", {})
                    zone = attrs.get("ZONE_SUBTY") or attrs.get("FLD_ZONE") or attrs.get("ZONE")
                    if zone:
                        flood_zones.append(zone)

            if not flood_zones:
                return FloodConditions(1.0, "fema", "zone_x", False)

            # Determine risk from zone
            zone_str = ", ".join(set(flood_zones))
            high_risk = any(z in zone_str for z in ["a", "ae", "ao", "ah", "ve", "v"])
            moderate_risk = any(z in zone_str for z in ["x500", "0.2 pct"])

            if high_risk:
                return FloodConditions(0.2, "fema", zone_str, True)
            elif moderate_risk:
                return FloodConditions(0.6, "fema", zone_str, True)

            return FloodConditions(0.9, "fema", zone_str, False)

        except (httpx.HTTPError, ValueError, KeyError):
            return FloodConditions(0.8, "fema", "query failed", False)


class NullFloodProvider(FloodProvider):
    async def get_conditions(self, location: Coordinate, at_time: datetime) -> FloodConditions:
        return FloodConditions()


def create_flood_provider(settings: Settings | None = None) -> FloodProvider:
    settings = settings or get_settings()
    # Could add config flag for flood data
    return FEMANFHLProvider(settings)
