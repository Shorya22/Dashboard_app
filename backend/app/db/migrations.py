"""
Startup migration runner — self-healing against a schema/version mismatch.

Normally `alembic upgrade head` is all a startup needs: it reads
`alembic_version`, applies whatever revisions are missing, and is a safe
no-op if already current. That assumption breaks for exactly one
historical case in this project: `app/db/session.py` used to run
`Base.metadata.create_all()` as a startup safety net, before the first
Alembic revision existed. Any local `app.db` created in that window has
the `users`/`sso_flows` tables already, but no `alembic_version` row —
so a plain `upgrade head` tries to `CREATE TABLE users` again and dies
with "table users already exists". Under `uvicorn --reload` that
exception kills the worker silently (the reloader just respawns it and
the same exception recurs), which looks exactly like the server hanging
forever with no listening socket and no visible traceback.

`run_startup_migrations` detects that one specific case — the target
tables already exist, but `alembic_version` doesn't have a row yet —
and heals it with `alembic stamp head` (record "already at head",
schema is authoritative) instead of `upgrade head` (which assumes the
schema is empty). Every other case (a truly fresh DB, or a DB already
on some real revision) goes through the normal `upgrade head` path
unchanged, so future real migrations are not silently skipped by this.
"""

from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.core.config import settings
from app.db.session import Base, engine

# Import side effect: registers every ORM model's table on Base.metadata.
# Without this, `Base.metadata.tables` is empty until something ELSE
# happens to import app.db.models first — which main.py's import order
# does not guarantee — and `_target_tables_already_exist` would silently
# treat "no models registered yet" the same as "no tables to check",
# skipping the self-heal it exists to do.
from app.db import models  # noqa: F401

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    return cfg


def _has_alembic_version_row() -> bool:
    inspector = inspect(engine)
    if "alembic_version" not in inspector.get_table_names():
        return False
    with engine.connect() as conn:
        row = conn.exec_driver_sql("SELECT 1 FROM alembic_version LIMIT 1").first()
    return row is not None


def _target_tables_already_exist() -> bool:
    """True if every table Alembic's models declare is already in the DB.

    Only tables genuinely OWNED by our ORM models count — a partial
    overlap (some tables present, some missing) is NOT this safe case;
    it goes through the normal `upgrade head` path so a real mismatch
    surfaces as a real error instead of being silently stamped over.
    """
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    declared = set(Base.metadata.tables.keys())
    return bool(declared) and declared.issubset(existing)


def run_startup_migrations() -> None:
    """Bring the DB schema to head, healing the pre-Alembic-adoption
    schema/version mismatch instead of crashing on it. Idempotent —
    safe to call on every startup."""
    cfg = _alembic_config()

    if not _has_alembic_version_row() and _target_tables_already_exist():
        logger.warning(
            "run_startup_migrations: schema already matches head but "
            "alembic_version has no row (a DB created before Alembic was "
            "adopted, or by the old Base.metadata.create_all() safety net) "
            "— stamping head instead of upgrading, no tables touched"
        )
        command.stamp(cfg, "head")
        return

    command.upgrade(cfg, "head")
