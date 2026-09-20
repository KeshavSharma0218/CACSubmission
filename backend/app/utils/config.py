"""
Central configuration for the SafeWalk backend.

Design decisions
-----------------
- We use pydantic-settings so every config value is validated at startup and can be
  overridden by environment variables (12-factor app style). If a required secret is
  missing, the app fails fast at boot instead of failing later mid-request.
- Nothing here is hardcoded to a specific city, provider, or API key. External services
  (Nominatim, Overpass, OSRM, weather, crime data) are configured through URLs/flags so
  they can be swapped for self-hosted or commercial alternatives without code changes.
- Rate-limit-related settings exist because several upstream services we depend on
  (notably Nominatim and the public Overpass instances) enforce strict usage policies.
  Baking the limits into config means the HTTP client layer (built in a later step) can
  throttle itself correctly instead of us discovering this in production via bans.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application-wide settings, populated from environment variables (or a `.env` file
    in local development). See `.env.example` for the full list of variables.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App metadata -----------------------------------------------------------
    app_name: str = "SafeWalk Backend"
    environment: Literal["development", "staging", "production", "test"] = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # --- Database -----------------------------------------------------------------
    # Async DSN, e.g. postgresql+asyncpg://safewalk:password@db:5432/safewalk
    # For Supabase, the database.py handles SSL via connect_args
    database_url: PostgresDsn = Field(
        default=PostgresDsn("postgresql+asyncpg://safewalk:safewalk@localhost:5432/safewalk")
    )
    db_echo: bool = False  # log SQL statements; useful in dev, noisy in prod
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # --- Auth (JWT) -----------------------------------------------------------
    jwt_secret_key: str = Field(default="dev-only-insecure-secret-change-me")
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 24

    # --- OpenStreetMap-family services -----------------------------------------
    nominatim_base_url: str = "https://nominatim.openstreetmap.org"
    nominatim_user_agent: str = "SafeWalk/0.1 (contact: set-a-real-contact-email)"
    nominatim_min_request_interval_seconds: float = 1.0

    overpass_base_url: str = "https://overpass-api.de/api/interpreter"
    overpass_timeout_seconds: int = 180

    # OSRM is the routing engine for candidate walking routes, scored by SafeWalk.
    # Public instance: https://router.project-osrm.org (rate-limited)
    # For production, self-host OSRM or use a commercial provider.
    osrm_base_url: str = "https://router.project-osrm.org"
    osrm_profile: str = "foot"
    max_route_alternatives: int = 10

    # Route safety lookups use a bounded corridor so a long route cannot trigger an
    # unexpectedly broad upstream or spatial query.
    route_safety_corridor_m: float = 150.0
    crime_lookback_days: int = 90

    # --- Weather (interface only for now; provider chosen later) -----------------
    weather_provider: Literal["none", "openweathermap", "nws"] = "nws"
    weather_api_key: str | None = None

    # --- Air quality (OpenAQ free tier) -----------------------------------------
    air_quality_provider: Literal["none", "openaq"] = "openaq"

    # --- Transit proximity (TransitLand free) -----------------------------------
    transit_provider: Literal["none", "transitland"] = "transitland"

    # --- Civic/311 data (Socrata city portals) ----------------------------------
    civic_data_provider: Literal["none", "socrata"] = "none"
    civic_data_base_url: str | None = None
    civic_data_dataset_id: str | None = None
    civic_data_api_key: str | None = None

    # --- Flood zones (FEMA NFHL free) -------------------------------------------
    flood_provider: Literal["none", "fema"] = "fema"

    # --- Crime data (provider-agnostic; concrete providers implement an interface) -
    crime_data_provider: str | None = None
    crime_data_api_key: str | None = None
    crime_data_base_url: str | None = None
    crime_data_dataset_id: str | None = None

    # --- HTTP and inbound protection ------------------------------------------
    http_timeout_seconds: float = 15.0
    http_max_retries: int = 2
    rate_limit: str = "60/minute"

    # --- CORS ------------------------------------------------------------------
    cors_allow_origins: list[str] = Field(default_factory=lambda: ["*"])

    # --- Logging -----------------------------------------------------------------
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_json: bool = True  # structured JSON logs in production, readable in dev if False

    @field_validator("database_url", mode="before")
    @classmethod
    def _ensure_asyncpg_driver(cls, v: str) -> str:
        """Guard against a plain `postgresql://` DSN being supplied, since we require
        the async asyncpg driver throughout the app."""
        if isinstance(v, str) and v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v


@lru_cache
def get_settings() -> Settings:
    """
    Cached settings accessor. Using a function (rather than a module-level singleton)
    lets us inject overrides cleanly in tests via dependency overrides, while still
    avoiding re-parsing environment variables on every call in normal operation.
    """
    return Settings()
