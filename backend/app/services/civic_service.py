"""311 / Civic service requests - non-emergency issues affecting safety.

Sources:
- City open data portals (Socrata-based)
- SeeClickFix API
- Open311 standard
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta

import httpx

from app.database.schemas import Coordinate
from app.utils.config import Settings, get_settings
from app.utils.http_client import get_json


@dataclass(slots=True)
class CivicConditions:
    """Normalized civic issue density: 0.0 = many issues, 1.0 = few issues."""

    score: float = 0.5
    source: str = "311"
    issue_count: int = 0
    categories: dict[str, int] | None = None


class CivicProvider(ABC):
    @abstractmethod
    async def get_conditions(self, location: Coordinate, at_time: datetime) -> CivicConditions: ...


class Socrata311Provider(CivicProvider):
    """Fetch 311 requests from city Socrata portal (e.g., NYC, Chicago, SF)."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        if not settings.civic_data_base_url or not settings.civic_data_dataset_id:
            raise ValueError("311 provider requires base URL and dataset ID")
        self.settings = settings
        self.client = client or httpx.AsyncClient(timeout=settings.http_timeout_seconds)

    async def get_conditions(self, location: Coordinate, at_time: datetime) -> CivicConditions:
        try:
            # Query 311 requests near location from last 30 days
            since = at_time - timedelta(days=30)
            radius_m = 1000  # 1km

            # Convert radius to approximate lat/lon degrees
            lat_delta = radius_m / 111000
            lon_delta = radius_m / (111000 * abs(location.lat))

            where = (
                f"created_date >= '{since.isoformat()}' "
                f"AND latitude BETWEEN {location.lat - lat_delta} AND {location.lat + lat_delta} "
                f"AND longitude BETWEEN {location.lon - lon_delta} AND {location.lon + lon_delta}"
            )

            params = {
                "$where": where,
                "$limit": 1000,
            }

            data = await get_json(
                self.client,
                f"{self.settings.civic_data_base_url.rstrip('/') if self.settings.civic_data_base_url else ''}/resource/{self.settings.civic_data_dataset_id}.json",
                params=params,
                headers={"X-App-Token": self.settings.civic_data_api_key}
                if self.settings.civic_data_api_key
                else None,
                retries=self.settings.http_max_retries,
            )

            if not data:
                return CivicConditions(0.8, "311", 0, {})

            # Categorize issues
            categories: dict[str, int] = {}
            safety_relevant = {
                "street light",
                "lighting",
                "pothole",
                "sidewalk",
                "crosswalk",
                "traffic signal",
                "sign",
                "graffiti",
                "abandoned",
                "vacant",
                "noise",
                "rodent",
                "trash",
                "debris",
                "flooding",
                "drainage",
            }

            for req in data:
                category = str(
                    req.get("complaint_type", req.get("service_request_type", "other"))
                ).lower()
                for key in safety_relevant:
                    if key in category:
                        categories[key] = categories.get(key, 0) + 1
                        break
                else:
                    categories["other"] = categories.get("other", 0) + 1

            total = len(data)
            safety_issues = sum(categories.values())

            # Score: fewer safety-relevant issues = safer
            score = max(0.0, 1.0 - min(safety_issues, 20) / 20)

            return CivicConditions(score, "311", total, categories)

        except (httpx.HTTPError, ValueError, KeyError):
            return CivicConditions(0.5, "311", 0, {})


class NullCivicProvider(CivicProvider):
    async def get_conditions(self, location: Coordinate, at_time: datetime) -> CivicConditions:
        return CivicConditions()


def create_civic_provider(settings: Settings | None = None) -> CivicProvider:
    settings = settings or get_settings()
    if settings.civic_data_provider == "socrata" and settings.civic_data_base_url:
        return Socrata311Provider(settings)
    return NullCivicProvider()
