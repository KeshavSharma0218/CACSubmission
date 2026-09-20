"""Crowdsourced hazard report endpoint with optional, non-enforcing JWT identity."""

import uuid

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from app.database.repositories import UserReportRepository
from app.database.schemas import UserReportCreate, UserReportRead
from app.utils.security import InvalidTokenError, decode_access_token

router = APIRouter(prefix="/reports", tags=["reports"])


def optional_user_id(authorization: str | None = Header(default=None)) -> uuid.UUID | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        return uuid.UUID(str(decode_access_token(authorization[7:]).get("sub")))
    except (InvalidTokenError, ValueError, TypeError):
        return None


@router.post(
    "",
    response_model=UserReportRead,
    status_code=201,
    summary="Submit a hazard report",
    description="Persists an anonymous report, or associates it with a user when a valid optional JWT is supplied.",
)
async def create_report(
    payload: UserReportCreate,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID | None = Depends(optional_user_id),
) -> UserReportRead:
    item = await UserReportRepository(db).create(payload, user_id)
    await db.commit()
    return UserReportRead.model_validate(item)


# Alias for backward compatibility - /report (singular)
@router.post(
    "/report",
    response_model=UserReportRead,
    status_code=201,
    include_in_schema=False,
)
async def create_report_alias(
    payload: UserReportCreate,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID | None = Depends(optional_user_id),
) -> UserReportRead:
    return await create_report(payload, db, user_id)


@router.get(
    "/nearby",
    response_model=list[UserReportRead],
    summary="Get nearby hazard reports",
    description="Returns active hazard reports within a radius of the given coordinates.",
)
async def get_nearby_reports(
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
    radius_m: float = Query(default=1000, ge=100, le=10000),
    db: AsyncSession = Depends(get_db),
) -> list[UserReportRead]:
    from app.database.schemas import Coordinate

    repo = UserReportRepository(db)
    reports = await repo.find_near(Coordinate(lat=lat, lon=lon), radius_m)
    active = [r for r in reports if r.status.value == "active"]
    return [UserReportRead.model_validate(r) for r in active]
