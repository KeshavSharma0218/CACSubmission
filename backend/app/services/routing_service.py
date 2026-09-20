"""OSRM-backed walking route candidates for SafeWalk.

This module deliberately no longer defines a routing-provider abstraction or custom
A* provider. SafeWalk currently generates a small candidate list through OSRM and
then scores those candidates in `route_safety_service.py`.
"""

from dataclasses import dataclass, field

import httpx

from app.database.schemas import Coordinate
from app.utils.config import Settings, get_settings
from app.utils.http_client import get_json


class NoRouteError(RuntimeError):
    pass


class NoSidewalkRouteError(NoRouteError):
    pass


@dataclass(slots=True)
class RouteResult:
    coordinates: list[Coordinate]
    distance_m: float
    duration_seconds: float
    safety_score: float = 0.5
    warnings: list[str] = field(default_factory=list)
    factor_breakdown: dict[str, float] = field(default_factory=dict)


class OSRMRoutingProvider:
    def __init__(self, settings: Settings | None = None, client: httpx.AsyncClient | None = None):
        self.settings = settings or get_settings()
        self.client = client or httpx.AsyncClient(timeout=self.settings.http_timeout_seconds)

    async def compute_routes(
        self, start: Coordinate, end: Coordinate, profile: str | None = None
    ) -> list[RouteResult]:
        configured_profile = self.settings.osrm_profile or profile or "foot"
        url = f"{self.settings.osrm_base_url.rstrip('/')}/route/v1/{configured_profile}/{start.lon},{start.lat};{end.lon},{end.lat}"
        desired = max(2, min(10, self.settings.max_route_alternatives))
        data = await get_json(
            self.client,
            url,
            params={
                "overview": "full",
                "geometries": "geojson",
                "alternatives": str(desired - 1),
            },
            retries=self.settings.http_max_retries,
        )
        if data.get("code") != "Ok" or not data.get("routes"):
            raise NoRouteError("No route connects those points.")
        return [
            RouteResult(
                [Coordinate(lat=p[1], lon=p[0]) for p in route["geometry"]["coordinates"]],
                float(route["distance"]),
                float(route["duration"]),
            )
            for route in data["routes"]
        ]


def create_routing_provider(settings: Settings | None = None) -> OSRMRoutingProvider:
    return OSRMRoutingProvider(settings or get_settings())
