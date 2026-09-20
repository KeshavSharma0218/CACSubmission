"""OSRM-backed walking route candidates for SafeWalk.

This module deliberately no longer defines a routing-provider abstraction or custom
A* provider. SafeWalk currently generates a small candidate list through OSRM and
then scores those candidates in `route_safety_service.py`.
"""

import logging
from dataclasses import dataclass, field

import httpx

from app.database.schemas import Coordinate
from app.utils.config import Settings, get_settings
from app.utils.http_client import get_json, UpstreamServiceError

logger = logging.getLogger(__name__)


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
        
        try:
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
        except UpstreamServiceError as exc:
            logger.error("osrm_request_failed", extra={"error": str(exc), "url": url})
            raise NoRouteError("Routing service is temporarily unavailable.") from exc

        # Check OSRM response code
        code = data.get("code")
        if code != "Ok":
            message = data.get("message", "Unknown error")
            logger.warning("osrm_returned_error", extra={"code": code, "message": message})
            if code == "NoRoute":
                raise NoRouteError("No route connects those points.")
            if code == "NoSegment":
                raise NoRouteError("No road segment found near the given coordinates.")
            raise NoRouteError(f"Routing failed: {message}")

        routes = data.get("routes")
        if not routes:
            raise NoRouteError("No route connects those points.")

        logger.info("osrm_routes_found", extra={"count": len(routes)})
        return [
            RouteResult(
                [Coordinate(lat=p[1], lon=p[0]) for p in route["geometry"]["coordinates"]],
                float(route["distance"]),
                float(route["duration"]),
            )
            for route in routes
        ]


def create_routing_provider(settings: Settings | None = None) -> OSRMRoutingProvider:
    return OSRMRoutingProvider(settings or get_settings())
