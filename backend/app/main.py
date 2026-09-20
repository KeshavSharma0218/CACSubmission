"""
SafeWalk backend - application entrypoint.

This module is intentionally thin: it wires together configuration, logging,
database lifecycle, exception handling, and routers. Business logic never lives
here - it lives in `app/services/*` and `app/routing/*`, which this module only
imports indirectly (via `app/api/routes.py`). Keeping `main.py` thin is what makes
the codebase easy to expand: new features are new files, not new code paths bolted
onto this one.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.types import ASGIApp

from app.api.routes import api_router
from app.database.database import init_postgis_extension
from app.utils.config import get_settings
from app.utils.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)
settings = get_settings()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple per-process IP limiter suitable for one free-tier API process."""

    def __init__(self, app: ASGIApp, limit: int = 60) -> None:
        super().__init__(app)
        self.limit = limit
        self.hits: dict[str, list[float]] = {}

    async def dispatch(self, request: Request, call_next):
        import time

        now = time.monotonic()
        key = request.client.host if request.client else "unknown"
        recent = [stamp for stamp in self.hits.get(key, []) if now - stamp < 60]
        if len(recent) >= self.limit:
            return JSONResponse(
                status_code=429, content={"detail": "Too many requests. Please try again later."}
            )
        recent.append(now)
        self.hits[key] = recent
        return await call_next(request)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan hook.

    On startup: ensures the PostGIS extension exists so a fresh database (e.g. right
    after `docker compose up` on a first run) is immediately usable without a manual
    migration step. On shutdown: nothing to clean up yet, but the hook is in place so
    future resources (e.g. a Redis connection pool) have an obvious place to close.
    """
    logger.info("startup", environment=settings.environment)
    try:
        await init_postgis_extension()
    except Exception as exc:  # noqa: BLE001
        # We deliberately don't crash the app if this fails - the /health endpoint
        # will report the DB as unreachable, which is more useful to an operator
        # than a container that won't start at all.
        logger.error("postgis_extension_setup_failed", error=str(exc))
    yield
    logger.info("shutdown")


app = FastAPI(
    title=settings.app_name,
    description=(
        "Backend API for SafeWalk - a pedestrian routing service that optimizes for "
        "safety (lighting, sidewalk availability, crime data, crowdsourced reports) "
        "rather than pure distance or speed."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware, limit=int(settings.rate_limit.split("/")[0]))


# --- Global exception handling -----------------------------------------------------
# These handlers ensure clients never see raw internal exception details (stack
# traces, DB error messages, etc.) - per the project's error-handling requirements -
# while the full detail is still captured in structured logs for debugging.


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    logger.warning("request_validation_failed", path=str(request.url), errors=exc.errors())
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Invalid request parameters.", "errors": exc.errors()},
    )


@app.exception_handler(HTTPException)
async def known_http_exception_handler(request: Request, exc: HTTPException) -> Response:
    # Re-uses FastAPI's default formatting for intentionally-raised HTTPExceptions
    # (these already carry a safe, client-appropriate message).
    return await http_exception_handler(request, exc)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "unhandled_exception",
        path=str(request.url),
        exc_type=type(exc).__name__,
        error=str(exc),
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal error occurred. Please try again later."},
    )


app.include_router(api_router, prefix=settings.api_v1_prefix)
