"""
Database engine and session management.

Design decisions
-----------------
- Fully async, using SQLAlchemy 2.x's async engine + asyncpg driver, so that FastAPI
  route handlers can `await` database calls instead of blocking the event loop -
  important once routing requests fan out into concurrent Overpass/OSRM/DB lookups.
- `get_db` is a FastAPI dependency (not a global session) so each request gets its own
  session with a clean transaction boundary, and sessions are never shared across
  concurrent requests.
- `Base` lives here (not in models.py) so both `database.py` and `models.py` can import
  it without a circular dependency; `models.py` (built in a later step) will import
  `Base` from this module.
- PostGIS-specific types come from GeoAlchemy2, which integrates with SQLAlchemy's
  metadata system - `Geometry` columns show up like any other typed column, and PostGIS
  spatial indexes/functions remain available through GeoAlchemy2's query helpers.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.utils.config import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models (see `app/database/models.py`)."""


def _build_engine() -> AsyncEngine:
    # Use SSL-enabled URL for Supabase/managed Postgres
    db_url = settings.database_url_with_ssl
    return create_async_engine(
        db_url,
        echo=settings.db_echo,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,  # avoids using a dead connection after DB restarts/idles
    )


engine: AsyncEngine = _build_engine()

async_session_factory = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a request-scoped async session.

    Usage:
        @router.get("/thing")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    """Context-manager variant for use outside of FastAPI's DI system (e.g. in
    background jobs or scripts that ingest OSM/crime data)."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_database_connection() -> bool:
    """
    Verifies both that the database is reachable and that PostGIS is installed.
    Used by the `/health` endpoint - a healthy process with an unreachable DB, or a
    DB missing the PostGIS extension, should both be reported as unhealthy.
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            result = await conn.execute(text("SELECT PostGIS_Version()"))
            version = result.scalar_one()
            logger.info("database_health_check_ok", postgis_version=version)
            return True
    except Exception as exc:  # noqa: BLE001 - deliberately broad: health check must not raise
        logger.error("database_health_check_failed", error=str(exc))
        return False


async def init_postgis_extension() -> None:
    """
    Ensures the PostGIS extension is enabled. Safe to call repeatedly (idempotent).
    Called once at application startup rather than relying on manual DBA setup, so a
    fresh `docker compose up` produces a fully working database with no extra steps.
    """
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        logger.info("postgis_extension_ensured")
