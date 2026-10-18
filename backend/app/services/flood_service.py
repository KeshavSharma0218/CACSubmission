"""Flood risk data from FEMA OpenFEMA API (free, no API key required).

OpenFEMA provides disaster declaration data at https://www.fema.gov/api/open
No subscription or API key is needed per FEMA documentation.

Falls back to neutral conditions when API is unavailable.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta

import httpx

from app.database.schemas import Coordinate
from app.utils.config import Settings, get_settings
from app.utils.http_client import UpstreamServiceError, get_json


@dataclass(slots=True)
class FloodConditions:
    """Normalized flood risk: 1.0 = no flood risk, 0.0 = high risk."""

    score: float = 1.0
    source: str = "fema"
    zone: str | None = None
    in_floodplain: bool = False


class FloodProvider(ABC):
    @abstractmethod
    async def get_conditions(self, location: Coordinate, at_time: datetime) -> FloodConditions: ...


class OpenFEMADisasterProvider(FloodProvider):
    """Query FEMA OpenFEMA for disaster declarations near a location.

    Uses DisasterDeclarationsSummaries entity to find recent flood-related
    disaster declarations. Returns elevated risk if there are recent flood
    declarations in the area.
    """

    BASE_URL = "https://www.fema.gov/api/open/v2"

    def __init__(self, settings: Settings | None = None, client: httpx.AsyncClient | None = None):
        self.settings = settings or get_settings()
        self.client = client or httpx.AsyncClient(timeout=self.settings.http_timeout_seconds)

    async def get_conditions(self, location: Coordinate, at_time: datetime) -> FloodConditions:
        try:
            # Get state from reverse geocode to filter declarations by state
            state = await self._get_state_from_coords(location)

            # Build OData filter for recent flood declarations
            # Look at declarations in the last 2 years
            two_years_ago = (at_time - timedelta(days=730)).strftime("%Y-%m-%d")

            if state:
                filter_str = (
                    f"incidentType eq 'Flood' and declarationDate ge "
                    f"'{two_years_ago}' and state eq '{state}'"
                )
            else:
                filter_str = (
                    f"incidentType eq 'Flood' and declarationDate ge "
                    f"'{two_years_ago}'"
                )

            params = {
                "$filter": filter_str,
                "$top": 50,
                "$format": "json",
            }

            data = await get_json(
                self.client,
                f"{self.BASE_URL}/DisasterDeclarationsSummaries",
                params=params,
                retries=self.settings.http_max_retries,
            )

            declarations = data.get("DisasterDeclarationsSummaries", [])
            count = len(declarations)

            if count == 0:
                return FloodConditions(1.0, "fema", "no recent flood declarations", False)

            # More recent declarations = higher risk
            # Count declarations in the last year
            one_year_ago = at_time - timedelta(days=365)
            recent_count = 0
            for decl in declarations:
                decl_date_str = decl.get("declarationDate", "")
                try:
                    decl_date = datetime.fromisoformat(decl_date_str.replace("Z", "+00:00"))
                    if decl_date.replace(tzinfo=None) > one_year_ago:
                        recent_count += 1
                except (ValueError, AttributeError):
                    continue

            if recent_count >= 3:
                score = 0.3  # High risk - frequent flooding
                zone = "frequent"
            elif recent_count >= 1:
                score = 0.6  # Moderate risk - some flooding
                zone = "occasional"
            else:
                score = 0.9  # Low risk - older declarations only
                zone = "historical"

            return FloodConditions(
                score,
                "fema",
                f"{zone}_flooding ({count} declarations)",
                recent_count > 0,
            )

        except (UpstreamServiceError, httpx.HTTPError, ValueError, KeyError):
            # OpenFEMA unavailable - return neutral
            return FloodConditions(0.8, "fema", "service unavailable", False)

    async def _get_state_from_coords(self, location: Coordinate) -> str | None:
        """Use reverse geocoding to get the state abbreviation."""
        try:
            data = await get_json(
                self.client,
                "https://nominatim.openstreetmap.org/reverse",
                params={
                    "lat": location.lat,
                    "lon": location.lon,
                    "format": "jsonv2",
                },
                headers={"User-Agent": self.settings.nominatim_user_agent},
                retries=1,
            )
            address = data.get("address", {})
            return address.get("state_code") or address.get("state")
        except (UpstreamServiceError, httpx.HTTPError, ValueError, KeyError):
            return None


class NullFloodProvider(FloodProvider):
    async def get_conditions(self, location: Coordinate, at_time: datetime) -> FloodConditions:
        return FloodConditions()


def create_flood_provider(settings: Settings | None = None) -> FloodProvider:
    settings = settings or get_settings()
    return OpenFEMADisasterProvider(settings)
