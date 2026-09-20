"""Safe Walk session endpoints: start, update location, stop, get status."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from app.database.repositories import SafeWalkLocationRepository, SafeWalkSessionRepository
from app.database.schemas import (
    SafeWalkRead,
    SafeWalkStartRequest,
    SafeWalkUpdateRequest,
    WalkStatus,
)
from app.utils.security import InvalidTokenError, decode_access_token

router = APIRouter(prefix="/safe-walk", tags=["safe-walk"])


async def get_current_user_id(
    authorization: str = Header(default=None), db: AsyncSession = Depends(get_db)
) -> uuid.UUID:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing or invalid token")
    try:
        payload = decode_access_token(authorization[7:])
        return uuid.UUID(payload.get("sub"))
    except (InvalidTokenError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")


@router.post(
    "/start",
    response_model=SafeWalkRead,
    status_code=status.HTTP_201_CREATED,
    summary="Start a Safe Walk session",
    description="Begins a new safe walk session with destination and optional expected arrival time.",
)
async def start_walk(
    request: SafeWalkStartRequest,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> SafeWalkRead:
    # Check for existing active session
    repo = SafeWalkSessionRepository(db)
    active = await repo.active_for_user(user_id)
    if active:
        raise HTTPException(status.HTTP_409_CONFLICT, "Already have an active safe walk session")

    session = await repo.create_for_user(user_id, request)
    await db.commit()
    return SafeWalkRead.model_validate(session)


@router.post(
    "/{session_id}/update",
    response_model=SafeWalkRead,
    summary="Update location during safe walk",
    description="Updates the user's current location during an active safe walk session.",
)
async def update_location(
    session_id: uuid.UUID,
    request: SafeWalkUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> SafeWalkRead:
    repo = SafeWalkSessionRepository(db)
    session = await repo.get_for_user(user_id, session_id)
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    if session.status != WalkStatus.active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Session is not active")

    session = await repo.update_location(session, request)

    # Also record in location history
    loc_repo = SafeWalkLocationRepository(db)
    await loc_repo.create(session_id, request.location)

    await db.commit()
    return SafeWalkRead.model_validate(session)


@router.post(
    "/{session_id}/stop",
    response_model=SafeWalkRead,
    summary="Stop a Safe Walk session",
    description="Ends the safe walk session.",
)
async def stop_walk(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> SafeWalkRead:
    repo = SafeWalkSessionRepository(db)
    session = await repo.get_for_user(user_id, session_id)
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    if session.status != WalkStatus.active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Session is not active")

    session.status = WalkStatus.ended
    session.ended_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(session)
    return SafeWalkRead.model_validate(session)


@router.get(
    "/active",
    response_model=SafeWalkRead | None,
    summary="Get active safe walk session",
    description="Returns the current active safe walk session for the user, if any.",
)
async def get_active(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> SafeWalkRead | None:
    repo = SafeWalkSessionRepository(db)
    session = await repo.active_for_user(user_id)
    if not session:
        return None
    return SafeWalkRead.model_validate(session)


@router.get(
    "/{session_id}",
    response_model=SafeWalkRead,
    summary="Get a safe walk session",
    description="Returns a specific safe walk session by ID.",
)
async def get_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> SafeWalkRead:
    repo = SafeWalkSessionRepository(db)
    session = await repo.get_for_user(user_id, session_id)
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    return SafeWalkRead.model_validate(session)
