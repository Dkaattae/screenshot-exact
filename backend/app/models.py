import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BodyProfile(Base):
    __tablename__ = "body_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    height_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    front_key: Mapped[str] = mapped_column(String(255))
    side_key: Mapped[str] = mapped_column(String(255))
    back_key: Mapped[str] = mapped_column(String(255))
    measurements: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DefaultBody(Base):
    __tablename__ = "default_bodies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(100))
    front_key: Mapped[str] = mapped_column(String(255))
    side_key: Mapped[str] = mapped_column(String(255))
    back_key: Mapped[str] = mapped_column(String(255))


class Background(Base):
    __tablename__ = "backgrounds"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    # Null for presets, which every user can see.
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    key: Mapped[str] = mapped_column(String(255))
    is_preset: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Item(Base):
    __tablename__ = "items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    slot: Mapped[str] = mapped_column(String(20), index=True)
    name: Mapped[str] = mapped_column(String(200))
    front_key: Mapped[str] = mapped_column(String(255))
    back_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    measurements: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Outfit(Base):
    __tablename__ = "outfits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    state: Mapped[dict[str, Any]] = mapped_column(JSON)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    outfit_id: Mapped[str] = mapped_column(
        ForeignKey("outfits.id", ondelete="CASCADE"), index=True
    )
    outfit_version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    # {view: {"status", "key", "inferred_item_ids"}}; "key" is a storage key, not a URL.
    views: Mapped[dict[str, Any]] = mapped_column(JSON)
    layers: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    # The outfit state this job renders, so later outfit edits don't change it.
    state: Mapped[dict[str, Any]] = mapped_column(JSON)
    total_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
