"""Routing and geocoding HTTP adapters; all work is delegated to services."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from app.database.repositories import UserReportRepository
from app.database.schemas import Coordinate
from app.services.crime_service import create_crime_provider
from app.services.osm_service import OSMService
from app.services.route_planner import RoutePlanner
from app.services.route_safety_service import RouteSafetyService
from app.services.routing_service import NoRouteError, NoSidewalkRouteError, create_routing_provider
from app.services.weather_service import create_weather_provider
from app.utils.http_client import UpstreamServiceError

router = APIRouter(tags=["routing"])


class RouteRequest(BaseModel):
    start: Coordinate
    destination: Coordinate
    preference: Literal["safest", "fastest", "balanced"] = "safest"
    require_sidewalk: bool = False
    return_alternatives: bool = False


class RouteResponse(BaseModel):
    polyline: str
    coordinates: list[Coordinate]
    distance_m: float
    estimated_walking_time_seconds: float
    safety_score: float = Field(ge=0, le=1)
    factor_breakdown: dict[str, float]
    warnings: list[str]


class RouteAlternativesResponse(BaseModel):
    routes: list[RouteResponse]
    selected_index: int


class GeocodeResponse(BaseModel):
    coordinate: Coordinate
    address: str


class ReverseGeocodeResponse(BaseModel):
    address: str


def get_route_planner(db: AsyncSession) -> RoutePlanner:
    return RoutePlanner(
        create_routing_provider(),
        RouteSafetyService(
            get_osm_service(),
            create_weather_provider(),
            create_crime_provider(),
            UserReportRepository(db),
        ),
    )


def get_osm_service() -> OSMService:
    return OSMService()


@router.post(
    "/route",
    response_model=RouteResponse | RouteAlternativesResponse,
    summary="Compute a pedestrian route",
    description="Returns a safety-aware pedestrian route between two validated WGS84 coordinates. Set return_alternatives=true to get all scored candidates.",
)
async def route(
    request: RouteRequest, db: AsyncSession = Depends(get_db)
) -> RouteResponse | RouteAlternativesResponse:
    try:
        result = await get_route_planner(db).plan(
            request.start,
            request.destination,
            request.preference,
            request.require_sidewalk,
            request.return_alternatives,
        )
        if request.return_alternatives:
            return RouteAlternativesResponse(**result)
        return RouteResponse(**result)
    except NoSidewalkRouteError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "No sidewalk-only route was found between those points."
        ) from exc
    except NoRouteError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "No route was found between those points."
        ) from exc
    except UpstreamServiceError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Routing is temporarily unavailable."
        ) from exc


@router.get(
    "/geocode",
    response_model=GeocodeResponse,
    summary="Geocode an address",
    description="Uses the configured OSM geocoder and respects its request-rate policy.",
)
async def geocode(address: str = Query(min_length=2, max_length=300)) -> GeocodeResponse:
    try:
        result = await get_osm_service().geocode(address)
    except UpstreamServiceError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Geocoding is temporarily unavailable."
        ) from exc
    if not result:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Address was not found.")
    return GeocodeResponse(coordinate=result[0], address=result[1])


@router.get(
    "/reverse-geocode",
    response_model=ReverseGeocodeResponse,
    summary="Reverse geocode coordinates",
    description="Returns a human-readable address for a validated WGS84 point.",
)
async def reverse_geocode(
    lat: float = Query(ge=-90, le=90), lon: float = Query(ge=-180, le=180)
) -> ReverseGeocodeResponse:
    try:
        address = await get_osm_service().reverse_geocode(Coordinate(lat=lat, lon=lon))
    except UpstreamServiceError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Geocoding is temporarily unavailable."
        ) from exc
    if not address:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Address was not found.")
    return ReverseGeocodeResponse(address=address)
