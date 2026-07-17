"""User lookup + dev-seed logic. Kept in services/ per project convention
that routes never touch persistence directly."""

from __future__ import annotations

import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.models import User, UserRole

logger = logging.getLogger(__name__)


class EmailAlreadyRegisteredError(Exception):
    """Raised by create_user when the email is already taken."""


def get_user_by_email(db: Session, email: str) -> User | None:
    # Normalize the query side so login is case-insensitive against
    # stored emails (which create_user normalizes to lowercase before
    # insert). Without this, registering as `Foo@bar.com` and later
    # logging in with the same casing would fail after normalization.
    return db.query(User).filter(User.email == email.strip().lower()).first()


def create_user(db: Session, email: str, plain_password: str) -> User:
    """Create a self-registered user. Role is hardcoded to `viewer` — the
    admin/viewer distinction is a schema-level artifact per PLAN.md
    Phase 3 and is deliberately not exposed to self-serve signup.

    Raises `EmailAlreadyRegisteredError` if the email is already taken.
    Uses a pre-check plus IntegrityError catch as a backstop for the
    (rare) race between two concurrent registrations of the same email —
    the unique index on `users.email` is the actual source of truth.
    """
    normalized_email = email.strip().lower()

    if get_user_by_email(db, normalized_email) is not None:
        raise EmailAlreadyRegisteredError(normalized_email)

    user = User(
        email=normalized_email,
        hashed_password=hash_password(plain_password),
        role=UserRole.viewer,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise EmailAlreadyRegisteredError(normalized_email) from exc
    db.refresh(user)
    logger.info("create_user: registered new user_id=%s", user.id)
    return user


def seed_dev_admin_if_empty(db: Session) -> None:
    """Seed exactly one dev-only admin user, only if the users table is
    empty (i.e. the DB was just created). Logs the credentials once so
    they're visible for local testing — this is a clearly-labeled
    dev-only account, not a silently hardcoded production secret."""
    if db.query(User).first() is not None:
        return

    user = User(
        email=settings.seed_admin_email,
        hashed_password=hash_password(settings.seed_admin_password),
        role=UserRole.admin,
    )
    db.add(user)
    db.commit()

    logger.warning(
        "Seeded dev-only admin user — email=%s password=%s "
        "(local dev only; change via SEED_ADMIN_EMAIL/SEED_ADMIN_PASSWORD env vars)",
        settings.seed_admin_email,
        settings.seed_admin_password,
    )
