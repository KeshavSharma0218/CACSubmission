"""Crime provider contract and optional Socrata reference adapter."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

import httpx

from app.database.schemas import Coordinate, CrimeIncidentData
from app.utils.config import Settings, get_settings
from app.utils.http_client import get_json


class CrimeDataProvider(ABC):
    @abstractmethod
    async def fetch_incidents(
        self, bbox: tuple[float, float, float, float], since: datetime
    ) -> list[CrimeIncidentData]: ...


class NullCrimeDataProvider(CrimeDataProvider):
    async def fetch_incidents(
        self, bbox: tuple[float, float, float, float], since: datetime
    ) -> list[CrimeIncidentData]:
        return []


class SocrataCrimeDataProvider(CrimeDataProvider):
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        if not settings.crime_data_base_url or not settings.crime_data_dataset_id:
            raise ValueError("Socrata provider requires base URL and dataset ID")
        self.base_url = settings.crime_data_base_url
        self.settings = settings
        self.client = client or httpx.AsyncClient(timeout=settings.http_timeout_seconds)

    async def fetch_incidents(
        self, bbox: tuple[float, float, float, float], since: datetime
    ) -> list[CrimeIncidentData]:
        south, west, north, east = bbox
        where = f"occurred_at >= '{since.isoformat()}' AND within_box(location,{north},{west},{south},{east})"
        rows: list[dict[str, Any]] = await get_json(
            self.client,
            f"{self.base_url.rstrip('/')}/resource/{self.settings.crime_data_dataset_id}.json",
            params={"$where": where, "$limit": 5000},
            headers={"X-App-Token": self.settings.crime_data_api_key}
            if self.settings.crime_data_api_key
            else None,
            retries=self.settings.http_max_retries,
        )
        result = []
        for row in rows:
            coords = row.get("location", {}).get("coordinates", [])
            if len(coords) == 2:
                result.append(
                    CrimeIncidentData(
                        location=Coordinate(lat=coords[1], lon=coords[0]),
                        category=str(row.get("category", "unknown")),
                        occurred_at=datetime.fromisoformat(str(row["occurred_at"])),
                        source_provider="socrata",
                        raw_data=row,
                    )
                )
        return result


def create_crime_provider(settings: Settings | None = None) -> CrimeDataProvider:
    settings = settings or get_settings()
    return (
        SocrataCrimeDataProvider(settings)
        if settings.crime_data_provider == "socrata"
        else NullCrimeDataProvider()
    )
