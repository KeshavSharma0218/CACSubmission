"""Async repositories centralize persistence and spatial-query details."""

import uuid
from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

from geoalchemy2 import Geography
from geoalchemy2.elements import WKTElement
from sqlalchemy import Select, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import models
from app.database.schemas import (
    Coordinate,
    CrimeIncidentData,
    FavoriteCreate,
    FeedbackCreate,
    SafeWalkStartRequest,
    SafeWalkUpdateRequest,
    SavedRouteCreate,
    TrustedContactCreate,
    UserCreate,
    UserReportCreate,
)

T = TypeVar("T")


def point(value: Coordinate) -> WKTElement:
    return WKTElement(f"POINT({value.lon} {value.lat})", srid=4326)


class Repository(Generic[T]):
    model: type[T]

    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, entity: T) -> T:
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def get_by_id(self, entity_id: uuid.UUID) -> T | None:
        return await self.session.get(self.model, entity_id)


class UserRepository(Repository[models.User]):
    model = models.User

    async def create(self, data: UserCreate) -> models.User:
        return await self.add(models.User(**data.model_dump()))

    async def get_by_email(self, email: str) -> models.User | None:
        return await self.session.scalar(select(self.model).where(self.model.email == email))


class TrustedContactRepository(Repository[models.TrustedContact]):
    model = models.TrustedContact

    async def create_for_user(
        self, user_id: uuid.UUID, data: TrustedContactCreate
    ) -> models.TrustedContact:
        return await self.add(models.TrustedContact(user_id=user_id, **data.model_dump()))

    async def list_for_user(self, user_id: uuid.UUID) -> list[models.TrustedContact]:
        return list(
            (
                await self.session.scalars(
                    select(self.model)
                    .where(self.model.user_id == user_id)
                    .order_by(self.model.created_at.desc())
                )
            ).all()
        )

    async def get_for_user(
        self, user_id: uuid.UUID, contact_id: uuid.UUID
    ) -> models.TrustedContact | None:
        return await self.session.scalar(
            select(self.model).where(self.model.id == contact_id, self.model.user_id == user_id)
        )


class SafeWalkSessionRepository(Repository[models.SafeWalkSession]):
    model = models.SafeWalkSession

    async def create_for_user(
        self, user_id: uuid.UUID, data: SafeWalkStartRequest
    ) -> models.SafeWalkSession:
        return await self.add(
            models.SafeWalkSession(
                user_id=user_id,
                destination=point(data.destination),
                expected_arrival_at=data.expected_arrival_at,
                status=models.WalkStatus.active,
                last_location=point(data.start_location),
                last_updated_at=datetime.now(UTC),
            )
        )

    async def active_for_user(self, user_id: uuid.UUID) -> models.SafeWalkSession | None:
        return await self.session.scalar(
            select(self.model)
            .where(self.model.user_id == user_id, self.model.status == models.WalkStatus.active)
            .order_by(self.model.started_at.desc())
            .limit(1)
        )

    async def get_for_user(
        self, user_id: uuid.UUID, session_id: uuid.UUID
    ) -> models.SafeWalkSession | None:
        return await self.session.scalar(
            select(self.model).where(self.model.id == session_id, self.model.user_id == user_id)
        )

    async def update_location(
        self, session: models.SafeWalkSession, data: SafeWalkUpdateRequest
    ) -> models.SafeWalkSession:
        session.last_location = point(data.location)
        session.last_updated_at = datetime.now(UTC)
        await self.session.flush()
        await self.session.refresh(session)
        return session


class SafeWalkLocationRepository(Repository[models.SafeWalkLocation]):
    model = models.SafeWalkLocation

    async def create(self, session_id: uuid.UUID, location: Coordinate) -> models.SafeWalkLocation:
        return await self.add(
            models.SafeWalkLocation(session_id=session_id, location=point(location))
        )


class UserReportRepository(Repository[models.UserReport]):
    model = models.UserReport

    async def create(
        self, data: UserReportCreate, user_id: uuid.UUID | None = None
    ) -> models.UserReport:
        return await self.add(
            models.UserReport(
                user_id=user_id,
                location=point(data.location),
                report_type=data.report_type,
                description=data.description,
            )
        )

    async def find_near(self, location: Coordinate, radius_m: float) -> list[models.UserReport]:
        stmt: Select[Any] = select(self.model).where(
            func.ST_DWithin(
                cast(self.model.location, Geography), cast(point(location), Geography), radius_m
            )
        )
        return list((await self.session.scalars(stmt)).all())


class RoadSegmentRepository(Repository[models.RoadSegment]):
    model = models.RoadSegment

    async def create(self, **values: Any) -> models.RoadSegment:
        return await self.add(models.RoadSegment(**values))

    async def list_with_latest_scores(self) -> list[models.RoadSegment]:
        return list((await self.session.scalars(select(self.model))).all())

    async def find_near(self, location: Coordinate, radius_m: float) -> list[models.RoadSegment]:
        stmt = select(self.model).where(
            func.ST_DWithin(
                cast(self.model.geometry, Geography), cast(point(location), Geography), radius_m
            )
        )
        return list((await self.session.scalars(stmt)).all())


class SafetyScoreRepository(Repository[models.SafetyScore]):
    model = models.SafetyScore

    async def create(
        self, road_segment_id: uuid.UUID, score: float, breakdown: dict[str, float]
    ) -> models.SafetyScore:
        return await self.add(
            models.SafetyScore(road_segment_id=road_segment_id, score=score, breakdown=breakdown)
        )


class CrimeIncidentRepository(Repository[models.CrimeIncident]):
    model = models.CrimeIncident

    async def create(self, data: CrimeIncidentData) -> models.CrimeIncident:
        return await self.add(
            models.CrimeIncident(
                location=point(data.location), **data.model_dump(exclude={"location"})
            )
        )

    async def find_near(self, location: Coordinate, radius_m: float) -> list[models.CrimeIncident]:
        stmt = select(self.model).where(
            func.ST_DWithin(
                cast(self.model.location, Geography), cast(point(location), Geography), radius_m
            )
        )
        return list((await self.session.scalars(stmt)).all())


class SavedRouteRepository(Repository[models.SavedRoute]):
    model = models.SavedRoute

    async def create(self, data: SavedRouteCreate) -> models.SavedRoute:
        return await self.add(
            models.SavedRoute(
                **data.model_dump(exclude={"start", "end"}),
                start=point(data.start),
                end=point(data.end),
            )
        )


class FeedbackRepository(Repository[models.Feedback]):
    model = models.Feedback

    async def create(self, data: FeedbackCreate) -> models.Feedback:
        return await self.add(models.Feedback(**data.model_dump()))


class FavoriteRepository(Repository[models.Favorite]):
    model = models.Favorite

    async def create(self, data: FavoriteCreate) -> models.Favorite:
        return await self.add(
            models.Favorite(**data.model_dump(exclude={"location"}), location=point(data.location))
        )
