"""Scores complete candidate routes using live and stored safety observations.

Route-level scoring is intentionally separate from graph edge scoring: it lets the
initial OSRM implementation compare alternatives today while the same normalized
factors can later populate the custom A* graph.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import ClassVar

from sqlalchemy.exc import SQLAlchemyError

from app.database.models import ReportType, UserReport
from app.database.repositories import UserReportRepository
from app.database.schemas import Coordinate
from app.routing.geometry import haversine_m
from app.services.air_quality_service import (
    AirQualityConditions,
    create_air_quality_provider,
)
from app.services.civic_service import CivicConditions, CivicProvider, create_civic_provider
from app.services.crime_service import CrimeDataProvider
from app.services.flood_service import FloodConditions, FloodProvider, create_flood_provider
from app.services.osm_service import OSMService
from app.services.routing_service import RouteResult
from app.services.traffic_service import TrafficConditions, TrafficProvider, create_traffic_provider
from app.services.transit_service import (
    TransitConditions,
    TransitProximity,
    create_transit_provider,
)
from app.services.weather_service import WeatherConditions, WeatherProvider
from app.utils.config import Settings, get_settings
from app.utils.http_client import UpstreamServiceError


def _clamp(value: float) -> float:
    """Clamp value to [0, 1] range."""
    return max(0.0, min(1.0, value))


class RouteSafetyService:
    """Combine normalized factors into an explainable score in the range [0, 1]."""

    weights: ClassVar[dict[str, float]] = {
        "crime": 0.20,
        "lighting": 0.15,
        "sidewalk": 0.15,
        "crosswalk": 0.07,
        "road_type": 0.08,
        "time_of_day": 0.07,
        "weather": 0.06,
        "traffic": 0.06,
        "air_quality": 0.05,
        "transit_proximity": 0.05,
        "civic_issues": 0.04,
        "flood_risk": 0.03,
        "user_reports": 0.04,
    }

    def __init__(
        self,
        osm: OSMService,
        weather: WeatherProvider,
        crime: CrimeDataProvider,
        reports: UserReportRepository | None = None,
        settings: Settings | None = None,
        traffic: TrafficProvider | None = None,
        air_quality: "AirQualityProvider" | None = None,
        transit: "TransitProvider" | None = None,
        civic: "CivicProvider" | None = None,
        flood: "FloodProvider" | None = None,
    ) -> None:
        # Use string annotations to avoid circular imports
        self.osm = osm
        self.weather = weather
        self.crime = crime
        self.reports = reports
        self.settings = settings or get_settings()
        # Initialize new providers (allow override for testing)
        from app.services.traffic_service import create_traffic_provider
        from app.services.air_quality_service import create_air_quality_provider
        from app.services.transit_service import create_transit_provider
        from app.services.civic_service import create_civic_provider
        from app.services.flood_service import create_flood_provider
        
        self.traffic = traffic or create_traffic_provider(self.settings)
        self.air_quality = air_quality or create_air_quality_provider(self.settings)
        self.transit = transit or create_transit_provider(self.settings)
        self.civic = civic or create_civic_provider(self.settings)
        self.flood = flood or create_flood_provider(self.settings)

    async def score_route(self, route: RouteResult, at_time: datetime) -> RouteResult:
        if not route.coordinates:
            return route
        bbox = self._bbox(route.coordinates)
        midpoint = route.coordinates[len(route.coordinates) // 2]
        radius = min(
            10_000.0,
            max(self.settings.route_safety_corridor_m, self._route_radius(route.coordinates)),
        )
        # Fetch all safety data concurrently
        features, weather, crimes, reports = await asyncio.gather(
            self._optional(self.osm.query_features(bbox), []),
            self._optional(self.weather.get_conditions(midpoint, at_time), WeatherConditions()),
            self._optional(
                self.crime.fetch_incidents(
                    bbox, at_time - timedelta(days=self.settings.crime_lookback_days)
                ),
                [],
            ),
            self._reports(midpoint, radius),
        )
        # Fetch new safety data concurrently
        traffic, air_quality, transit, civic, flood = await asyncio.gather(
            self._optional(self.traffic.get_conditions(midpoint, at_time), TrafficConditions()),
            self._optional(
                self.air_quality.get_conditions(midpoint, at_time), AirQualityConditions()
            ),
            self._optional(self.transit.get_proximity(midpoint, at_time), TransitProximity()),
            self._optional(self.civic.get_conditions(midpoint, at_time), CivicConditions()),
            self._optional(self.flood.get_conditions(midpoint, at_time), FloodConditions()),
        )
        # Compute all factor scores
        breakdown = self._factor_scores(
            features, weather, len(crimes), reports, at_time,
            traffic, air_quality, transit, civic, flood
        )
        route.factor_breakdown = breakdown
        route.safety_score = round(
            sum(breakdown[name] * weight for name, weight in self.weights.items()), 3
        )
        route.warnings = self._warnings(breakdown)
        return route

    @staticmethod
    async def _optional(awaitable, fallback):
        try:
            return await awaitable
        except UpstreamServiceError:
            return fallback

    async def _reports(self, midpoint: Coordinate, radius: float) -> list[UserReport]:
        if self.reports is None:
            return []
        try:
            return await self.reports.find_near(midpoint, radius)
        except SQLAlchemyError:
            # Reporting data enriches routing but must not make route generation
            # unavailable during a transient database problem.
            return []

    @staticmethod
    def _bbox(points: list[Coordinate]) -> tuple[float, float, float, float]:
        padding = 0.0015
        return (
            min(p.lat for p in points) - padding,
            min(p.lon for p in points) - padding,
            max(p.lat for p in points) + padding,
            max(p.lon for p in points) + padding,
        )

    @staticmethod
    def _route_radius(points: list[Coordinate]) -> float:
        midpoint = points[len(points) // 2]
        return max(haversine_m(midpoint, points[0]), haversine_m(midpoint, points[-1]))

    @staticmethod
    def _factor_scores(
        features,
        weather,
        crime_count,
        reports,
        at_time,
        traffic: TrafficConditions,
        air_quality: AirQualityConditions,
        transit: TransitConditions,
        civic: CivicConditions,
        flood: FloodConditions,
    ):
        ways = [item for item in features if item.get("type") == "way"]
        nodes = [item for item in features if item.get("type") == "node"]
        tags = [item.get("tags", {}) for item in ways]
        lit_known = [tag for tag in tags if "lit" in tag]
        sidewalk_known = [
            tag for tag in tags if "sidewalk" in tag or tag.get("highway") == "footway"
        ]
        lighting = (
            sum(tag.get("lit") in {"yes", "24/7"} for tag in lit_known) / len(lit_known)
            if lit_known
            else 0.5
        )
        sidewalk = (
            sum(
                tag.get("sidewalk") not in {"no", "none"} or tag.get("highway") == "footway"
                for tag in sidewalk_known
            )
            / len(sidewalk_known)
            if sidewalk_known
            else 0.5
        )
        crossings = sum(item.get("tags", {}).get("highway") == "crossing" for item in nodes)
        pedestrian_types = {"footway", "pedestrian", "path", "living_street", "residential"}
        road_type = (
            sum(tag.get("highway") in pedestrian_types for tag in tags) / len(tags) if tags else 0.5
        )
        active_reports = sum(
            getattr(report, "status", "active") == "active"
            or getattr(getattr(report, "status", None), "value", None) == "active"
            for report in reports
        )
        severe_reports = sum(
            getattr(report, "report_type", None)
            in {ReportType.unsafe_activity, ReportType.aggressive_animal}
            for report in reports
        )
        # All scores clamped to [0, 1]
        return {
            "crime": _clamp(1.0 - min(crime_count, 20) / 20),
            "lighting": _clamp(lighting),
            "sidewalk": _clamp(sidewalk),
            "crosswalk": _clamp(min(1.0, 0.5 + crossings / 10)),  # Was missing clamp
            "road_type": _clamp(road_type),
            "time_of_day": _clamp(1.0 if 6 <= at_time.hour < 20 else (0.75 if lighting >= 0.7 else 0.35)),
            "weather": _clamp(1.0 - weather.severity),
            "traffic": _clamp(1.0 - traffic.level),
            "air_quality": _clamp(air_quality.aqi),
            "transit_proximity": _clamp(transit.score),
            "civic_issues": _clamp(civic.score),
            "flood_risk": _clamp(flood.score),
            "user_reports": _clamp(1.0 - min(active_reports + severe_reports, 10) / 10),
        }

    @staticmethod
    def _warnings(scores: dict[str, float]) -> list[str]:
        labels = {
            "crime": "Recent crime activity was reported near this route.",
            "lighting": "Parts of this route may have limited lighting.",
            "sidewalk": "Sidewalk coverage may be incomplete.",
            "crosswalk": "Crosswalk coverage may be limited.",
            "weather": "Current weather may make walking less safe.",
            "traffic": "High traffic volume on this route.",
            "air_quality": "Poor air quality on this route.",
            "transit_proximity": "Far from transit stops - fewer people around.",
            "civic_issues": "Multiple civic issues reported in this area.",
            "flood_risk": "Route passes through a flood-prone area.",
            "user_reports": "Active community hazards were reported near this route.",
        }
        return [message for name, message in labels.items() if scores[name] < 0.5]
