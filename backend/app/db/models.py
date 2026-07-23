"""SQLAlchemy ORM models. Phase 3 adds the first real table: `users`."""

from __future__ import annotations

import datetime
import enum
import uuid

from sqlalchemy import DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    viewer = "viewer"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    # For SSO users this is a hash of a random, never-issued value (not a
    # real password) — kept NOT NULL rather than made nullable so no
    # SQLite column-nullability migration is needed. auth_provider is the
    # actual signal for whether password login should be allowed.
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False, default=UserRole.viewer)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    auth_provider: Mapped[str] = mapped_column(String(20), nullable=False, default="local")
    # Azure `oid` claim — stable per-user identifier from Entra ID. No DB
    # uniqueness constraint here: SQLite's ALTER TABLE ADD COLUMN can't add
    # one after the fact, so uniqueness is enforced at the lookup layer
    # (get_or_create_sso_user) instead.
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)
