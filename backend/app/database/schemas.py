"""Validated API/database transfer objects, deliberately separate from ORM state."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.database.models import ReportStatus, ReportType, WalkStatus


class Coordinate(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    hashed_password: str = Field(min_length=1, max_length=255)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    display_name: str | None = None
    phone_number: str | None = None
    created_at: datetime


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=72)  # bcrypt max 72 bytes
    display_name: str | None = Field(default=None, max_length=120)
    phone_number: str | None = Field(default=None, max_length=30)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=72)  # bcrypt max 72 bytes


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class TrustedContactCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone_number: str = Field(min_length=7, max_length=30)
    relation: str | None = Field(default=None, max_length=80)


class TrustedContactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    phone_number: str
    relation: str | None = None
    is_active: bool = True
    created_at: datetime


class SafeWalkStartRequest(BaseModel):
    start_location: Coordinate
    destination: Coordinate
    expected_arrival_at: datetime | None = None


class SafeWalkUpdateRequest(BaseModel):
    location: Coordinate


class SafeWalkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID
    status: WalkStatus
    destination: Coordinate | None = None
    last_location: Coordinate | None = None
    started_at: datetime
    ended_at: datetime | None = None
    last_updated_at: datetime | None = None
    expected_arrival_at: datetime | None = None


class UserReportCreate(BaseModel):
    location: Coordinate
    report_type: ReportType
    description: str | None = Field(default=None, max_length=2000)


class UserReportRead(UserReportCreate):
    id: uuid.UUID
    user_id: uuid.UUID | None
    created_at: datetime
    status: ReportStatus


class SafetyScoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    road_segment_id: uuid.UUID
    score: float
    breakdown: dict[str, float]
    computed_at: datetime


class CrimeIncidentData(BaseModel):
    location: Coordinate
    category: str
    occurred_at: datetime
    source_provider: str
    raw_data: dict[str, Any] = Field(default_factory=dict)


class SavedRouteCreate(BaseModel):
    user_id: uuid.UUID
    start: Coordinate
    end: Coordinate
    polyline: str
    name: str = Field(min_length=1, max_length=120)


class FavoriteCreate(BaseModel):
    user_id: uuid.UUID
    location: Coordinate
    label: str = Field(min_length=1, max_length=120)


class FeedbackCreate(BaseModel):
    user_id: uuid.UUID | None = None
    route_id: uuid.UUID | None = None
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)
