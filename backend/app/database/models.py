"""Persistent domain models; spatial data stays in WGS84 for API interoperability."""

import enum
import uuid
from datetime import datetime
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base


class ReportType(str, enum.Enum):
    poor_lighting = "poor_lighting"
    construction = "construction"
    aggressive_animal = "aggressive_animal"
    unsafe_activity = "unsafe_activity"
    broken_sidewalk = "broken_sidewalk"
    other = "other"


class ReportStatus(str, enum.Enum):
    active = "active"
    resolved = "resolved"
    expired = "expired"


class WalkStatus(str, enum.Enum):
    active = "active"
    alerted = "alerted"
    ended = "ended"
    cancelled = "cancelled"


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TrustedContact(Base):
    __tablename__ = "trusted_contacts"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    phone_number: Mapped[str] = mapped_column(String(30))
    relation: Mapped[str | None] = mapped_column(String(80), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SafeWalkSession(Base):
    __tablename__ = "safe_walk_sessions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[WalkStatus] = mapped_column(
        Enum(WalkStatus, name="walk_status"), default=WalkStatus.active
    )
    destination: Mapped[Any] = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=False), nullable=True
    )
    last_location: Mapped[Any] = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=False), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expected_arrival_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    __table_args__ = (
        Index("ix_safe_walk_sessions_destination_gist", destination, postgresql_using="gist"),
        Index("ix_safe_walk_sessions_last_location_gist", last_location, postgresql_using="gist"),
    )


class SafeWalkLocation(Base):
    __tablename__ = "safe_walk_locations"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("safe_walk_sessions.id", ondelete="CASCADE"), index=True
    )
    location: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326, spatial_index=False))
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    __table_args__ = (
        Index("ix_safe_walk_locations_location_gist", location, postgresql_using="gist"),
    )


class SavedRoute(Base):
    __tablename__ = "saved_routes"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    start: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326, spatial_index=False))
    end: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326, spatial_index=False))
    polyline: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        Index("ix_saved_routes_start_gist", start, postgresql_using="gist"),
        Index("ix_saved_routes_end_gist", end, postgresql_using="gist"),
    )


class RoadSegment(Base):
    __tablename__ = "road_segments"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    osm_way_id: Mapped[int] = mapped_column(Integer, index=True)
    geometry: Mapped[Any] = mapped_column(Geometry("LINESTRING", srid=4326, spatial_index=False))
    road_type: Mapped[str] = mapped_column(String(50), default="unknown")
    has_sidewalk: Mapped[bool] = mapped_column(Boolean, default=False)
    is_lit: Mapped[bool] = mapped_column(Boolean, default=False)
    speed_kph: Mapped[float | None] = mapped_column(Float, nullable=True)
    traffic_level: Mapped[float | None] = mapped_column(Float, nullable=True)
    scores: Mapped[list["SafetyScore"]] = relationship(
        back_populates="road_segment", cascade="all, delete-orphan"
    )
    __table_args__ = (Index("ix_road_segments_geometry_gist", geometry, postgresql_using="gist"),)


class SafetyScore(Base):
    __tablename__ = "safety_scores"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    road_segment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("road_segments.id", ondelete="CASCADE"), index=True
    )
    score: Mapped[float] = mapped_column(Float)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    breakdown: Mapped[dict[str, float]] = mapped_column(JSONB, default=dict)
    road_segment: Mapped[RoadSegment] = relationship(back_populates="scores")


class CrimeIncident(Base):
    __tablename__ = "crime_incidents"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    location: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326, spatial_index=False))
    category: Mapped[str] = mapped_column(String(100))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source_provider: Mapped[str] = mapped_column(String(80))
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    __table_args__ = (Index("ix_crime_incidents_location_gist", location, postgresql_using="gist"),)


class UserReport(Base):
    __tablename__ = "user_reports"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    location: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326, spatial_index=False))
    report_type: Mapped[ReportType] = mapped_column(Enum(ReportType, name="report_type"))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    status: Mapped[ReportStatus] = mapped_column(
        Enum(ReportStatus, name="report_status"), default=ReportStatus.active
    )
    __table_args__ = (Index("ix_user_reports_location_gist", location, postgresql_using="gist"),)


class Feedback(Base):
    __tablename__ = "feedback"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    route_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("saved_routes.id", ondelete="SET NULL"), nullable=True
    )
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Favorite(Base):
    __tablename__ = "favorites"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    location: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326, spatial_index=False))
    label: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (Index("ix_favorites_location_gist", location, postgresql_using="gist"),)
