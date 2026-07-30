"""
SQLAlchemy engine/session setup.

Phase 3 introduces the first real table (`users`). Local dev only, per
CLAUDE.md — no Azure/AWS setup yet — so a SQLite file at
`backend/app/data/app.db` is the lightest-weight option that's still a
real database (not a stub/in-memory dict). `backend/alembic/` is
scaffolded per api-conventions for "once a real DB exists"; schema is
brought to head by `app/db/migrations.py:run_startup_migrations` at
app startup, which also heals the one-time case of a local `app.db`
that predates Alembic's adoption (created by an earlier, now-removed
`Base.metadata.create_all()` startup safety net) — see that module's
docstring.
"""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

# Ensure the sqlite file's parent directory exists before engine creation.
if settings.database_url.startswith("sqlite:///./"):
    db_path = settings.database_url.replace("sqlite:///./", "", 1)
    abs_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), db_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Session:
    """FastAPI dependency yielding a request-scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
