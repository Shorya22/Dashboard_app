"""User lookup + dev-seed logic. Kept in services/ per project convention
that routes never touch persistence directly."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.models import User, UserRole

logger = logging.getLogger(__name__)


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


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
