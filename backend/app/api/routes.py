"""
Top-level API router.

This module aggregates all versioned sub-routers (health, and later: routing, geocode,
reports, users) into a single `api_router` that `main.py` mounts under the configured
prefix. Keeping this file as a pure aggregator - rather than putting endpoint logic
here - means adding a new resource (e.g. `reports.py`) is a one-line `include_router`
call and doesn't touch existing route files.
"""

from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.auth import router as auth_router
from app.api.reports import router as reports_router
from app.api.routing import router as routing_router
from app.api.safe_walk import router as safe_walk_router
from app.api.trusted_contacts import router as trusted_contacts_router
from app.database.database import check_database_connection
from app.utils.config import get_settings

api_router = APIRouter()
api_router.include_router(routing_router)
api_router.include_router(reports_router)
api_router.include_router(auth_router)
api_router.include_router(trusted_contacts_router)
api_router.include_router(safe_walk_router)


class HealthResponse(BaseModel):
    """Response body for `/health`."""

    status: str
    environment: str
    database_connected: bool
    timestamp: datetime


@api_router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description=(
        "Reports whether the API process is up and whether it can reach PostgreSQL/"
        "PostGIS. Intended for use by container orchestrators, load balancers, and "
        "uptime monitors. Does not require authentication."
    ),
    tags=["system"],
)
async def health_check() -> HealthResponse:
    settings = get_settings()
    db_ok = await check_database_connection()
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        environment=settings.environment,
        database_connected=db_ok,
        timestamp=datetime.now(UTC),
    )
