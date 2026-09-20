"""Authentication endpoints: register, login, and current user."""

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from app.database.repositories import UserRepository
from app.database.schemas import LoginRequest, RegisterRequest, TokenResponse, UserRead
from app.utils.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Creates a new user account and returns an access token.",
)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    repo = UserRepository(db)
    existing = await repo.get_by_email(request.email)
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    from app.database.schemas import UserCreate

    user = await repo.create(
        UserCreate(
            email=request.email,
            hashed_password=hash_password(request.password),
        )
    )
    # Update optional fields after creation
    if request.display_name:
        user.display_name = request.display_name
    if request.phone_number:
        user.phone_number = request.phone_number
    await db.commit()

    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token, user=UserRead.model_validate(user))


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in",
    description="Authenticates a user and returns an access token.",
)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    repo = UserRepository(db)
    user = await repo.get_by_email(request.email)
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token, user=UserRead.model_validate(user))


@router.get(
    "/me",
    response_model=UserRead,
    summary="Get current user",
    description="Returns the authenticated user's profile.",
)
async def me(
    authorization: str = Header(default=None), db: AsyncSession = Depends(get_db)
) -> UserRead:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing or invalid token")

    import uuid

    from app.utils.security import InvalidTokenError, decode_access_token

    try:
        payload = decode_access_token(authorization[7:])
        user_id = uuid.UUID(payload.get("sub"))
    except (InvalidTokenError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")

    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    return UserRead.model_validate(user)
