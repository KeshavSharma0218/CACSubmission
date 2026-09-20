"""Trusted contacts endpoints: CRUD for user's emergency contacts."""

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from app.database.repositories import TrustedContactRepository
from app.database.schemas import TrustedContactCreate, TrustedContactRead
from app.utils.security import InvalidTokenError, decode_access_token

router = APIRouter(prefix="/trusted-contacts", tags=["trusted-contacts"])


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
    "",
    response_model=TrustedContactRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a trusted contact",
    description="Creates a new trusted contact for the authenticated user.",
)
async def create_contact(
    request: TrustedContactCreate,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> TrustedContactRead:
    repo = TrustedContactRepository(db)
    contact = await repo.create_for_user(user_id, request)
    await db.commit()
    return TrustedContactRead.model_validate(contact)


@router.get(
    "",
    response_model=list[TrustedContactRead],
    summary="List trusted contacts",
    description="Returns all trusted contacts for the authenticated user.",
)
async def list_contacts(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> list[TrustedContactRead]:
    repo = TrustedContactRepository(db)
    contacts = await repo.list_for_user(user_id)
    return [TrustedContactRead.model_validate(c) for c in contacts]


@router.get(
    "/{contact_id}",
    response_model=TrustedContactRead,
    summary="Get a trusted contact",
    description="Returns a specific trusted contact by ID.",
)
async def get_contact(
    contact_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> TrustedContactRead:
    repo = TrustedContactRepository(db)
    contact = await repo.get_for_user(user_id, contact_id)
    if not contact:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contact not found")
    return TrustedContactRead.model_validate(contact)


@router.delete(
    "/{contact_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a trusted contact",
    description="Removes a trusted contact.",
)
async def delete_contact(
    contact_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> None:
    repo = TrustedContactRepository(db)
    contact = await repo.get_for_user(user_id, contact_id)
    if not contact:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contact not found")
    await db.delete(contact)
    await db.commit()
