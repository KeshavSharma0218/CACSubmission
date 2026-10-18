"""Rate-conscious Nominatim and Overpass access behind one OSM-facing service."""

import asyncio
import time
from typing import Any

import httpx

from app.database.schemas import Coordinate
from app.utils.config import Settings, get_settings
from app.utils.http_client import UpstreamServiceError, get_json


class OSMService:
    # Multiple Overpass instances for fallback
    OVERPASS_INSTANCES = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://overpass.nchc.org.tw/api/interpreter",
    ]

    def __init__(self, settings: Settings | None = None, client: httpx.AsyncClient | None = None):
        self.settings = settings or get_settings()
        self._client = client
        self._lock = asyncio.Lock()
        self._last_nominatim = 0.0

    async def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.settings.http_timeout_seconds)
        return self._client

    async def _nominatim(self, path: str, params: dict[str, Any]) -> Any:
        async with self._lock:
            delay = self.settings.nominatim_min_request_interval_seconds - (
                time.monotonic() - self._last_nominatim
            )
            if delay > 0:
                await asyncio.sleep(delay)
            try:
                return await get_json(
                    await self._http(),
                    f"{self.settings.nominatim_base_url.rstrip('/')}/{path}",
                    params=params,
                    headers={"User-Agent": self.settings.nominatim_user_agent},
                    retries=self.settings.http_max_retries,
                )
            finally:
                self._last_nominatim = time.monotonic()

    async def geocode(self, address: str) -> tuple[Coordinate, str] | None:
        data = await self._nominatim("search", {"q": address, "format": "jsonv2", "limit": 1})
        if not data:
            return None
        return Coordinate(lat=float(data[0]["lat"]), lon=float(data[0]["lon"])), data[0].get(
            "display_name", address
        )

    async def reverse_geocode(self, location: Coordinate) -> str | None:
        data = await self._nominatim(
            "reverse", {"lat": location.lat, "lon": location.lon, "format": "jsonv2"}
        )
        return data.get("display_name") if isinstance(data, dict) else None

    async def query_features(self, bbox: tuple[float, float, float, float]) -> list[dict[str, Any]]:
        south, west, north, east = bbox
        query = f'[out:json][timeout:{self.settings.overpass_timeout_seconds}];(way["highway"]({south},{west},{north},{east});node["highway"="crossing"]({south},{west},{north},{east});node["man_made"="street_lamp"]({south},{west},{north},{east}););out geom;'
        # Overpass requires Accept header for JSON response
        headers = {"Accept": "application/json"}

        last_error = None
        for base_url in self.OVERPASS_INSTANCES:
            try:
                data = await get_json(
                    await self._http(),
                    base_url,
                    params={"data": query},
                    headers=headers,
                    retries=self.settings.http_max_retries,
                )
                return data.get("elements", [])
            except UpstreamServiceError as exc:
                last_error = exc
                continue  # Try next instance

        # All instances failed - return empty instead of crashing
        return []
