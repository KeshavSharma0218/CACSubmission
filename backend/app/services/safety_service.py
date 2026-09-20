"""Composable, explainable safety scoring; factors are independent plugin objects."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from app.database.models import RoadSegment
from app.database.repositories import SafetyScoreRepository
from app.services.weather_service import WeatherConditions


@dataclass(slots=True)
class ScoringContext:
    at_time: datetime
    crime_count: int = 0
    has_crosswalk: bool = False
    weather: WeatherConditions | None = None
    traffic_level: float = 0.0
    air_quality: float = 0.7
    transit_proximity: float = 0.5
    civic_issues: float = 0.5
    flood_risk: float = 1.0


class SafetyFactor(ABC):
    name: str

    @abstractmethod
    async def score(self, segment: RoadSegment, context: ScoringContext) -> float: ...


class CrimeFactor(SafetyFactor):
    name = "crime"

    async def score(self, segment: RoadSegment, context: ScoringContext) -> float:
        return max(0.0, 1.0 - min(context.crime_count, 10) / 10)


class LightingFactor(SafetyFactor):
    name = "lighting"

    async def score(self, segment: RoadSegment, context: ScoringContext) -> float:
        return 1.0 if segment.is_lit else 0.25


class SidewalkFactor(SafetyFactor):
    name = "sidewalk"

    async def score(self, segment: RoadSegment, context: ScoringContext) -> float:
        return 1.0 if segment.has_sidewalk else 0.3


class CrosswalkFactor(SafetyFactor):
    name = "crosswalk"

    async def score(self, segment: RoadSegment, context: ScoringContext) -> float:
        return 1.0 if context.has_crosswalk else 0.5


class RoadTypeFactor(SafetyFactor):
    name = "road_type"

    async def score(self, segment: RoadSegment, context: ScoringContext) -> float:
        return {"footway": 1.0, "pedestrian": 1.0, "residential": 0.8, "primary": 0.35}.get(
            segment.road_type, 0.6
        )


class TimeOfDayFactor(SafetyFactor):
    name = "time_of_day"

    async def score(self, segment: RoadSegment, context: ScoringContext) -> float:
        return 1.0 if 6 <= context.at_time.hour < 20 else (0.8 if segment.is_lit else 0.35)


class WeatherFactor(SafetyFactor):
    name = "weather"

    async def score(self, segment: RoadSegment, context: ScoringContext) -> float:
        return max(0.0, 1.0 - (context.weather.severity if context.weather else 0.0))


class TrafficFactor(SafetyFactor):
    name = "traffic"

    async def score(self, segment: RoadSegment, context: ScoringContext) -> float:
        # Lower traffic = safer (less vehicle conflict)
        return max(0.0, 1.0 - context.traffic_level)


class AirQualityFactor(SafetyFactor):
    name = "air_quality"

    async def score(self, segment: RoadSegment, context: ScoringContext) -> float:
        return context.air_quality


class TransitProximityFactor(SafetyFactor):
    name = "transit_proximity"

    async def score(self, segment: RoadSegment, context: ScoringContext) -> float:
        # Closer to transit = more people, better lighting, safer
        return context.transit_proximity


class CivicIssuesFactor(SafetyFactor):
    name = "civic_issues"

    async def score(self, segment: RoadSegment, context: ScoringContext) -> float:
        return context.civic_issues


class FloodRiskFactor(SafetyFactor):
    name = "flood_risk"

    async def score(self, segment: RoadSegment, context: ScoringContext) -> float:
        return context.flood_risk


class NeutralFactor(SafetyFactor):
    """Explicit neutral placeholder for factors awaiting a trustworthy data source."""

    def __init__(self, name: str):
        self.name = name

    async def score(self, segment: RoadSegment, context: ScoringContext) -> float:
        return 0.5  # TODO: needs a data source


class SafetyService:
    def __init__(
        self,
        repository: SafetyScoreRepository | None,
        factors: list[SafetyFactor] | None = None,
        weights: dict[str, float] | None = None,
    ):
        self.repository = repository
        self.factors = factors or [
            CrimeFactor(),
            LightingFactor(),
            SidewalkFactor(),
            CrosswalkFactor(),
            RoadTypeFactor(),
            TimeOfDayFactor(),
            WeatherFactor(),
            TrafficFactor(),
            AirQualityFactor(),
            TransitProximityFactor(),
            CivicIssuesFactor(),
            FloodRiskFactor(),
            NeutralFactor("user_reports"),
            NeutralFactor("visibility"),
        ]
        self.weights = weights or {factor.name: 1.0 for factor in self.factors}

    async def score_segment(
        self, segment: RoadSegment, context: ScoringContext, persist: bool = True
    ) -> tuple[float, dict[str, float]]:
        breakdown = {
            factor.name: min(1.0, max(0.0, await factor.score(segment, context)))
            for factor in self.factors
        }
        total_weight = sum(self.weights.get(name, 1.0) for name in breakdown)
        score = (
            sum(value * self.weights.get(name, 1.0) for name, value in breakdown.items())
            / total_weight
            if total_weight
            else 0.5
        )
        if persist and self.repository and segment.id:
            await self.repository.create(segment.id, score, breakdown)
        return score, breakdown
