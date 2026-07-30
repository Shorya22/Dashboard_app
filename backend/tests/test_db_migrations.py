"""
Tests for app/db/migrations.py — specifically the self-healing path for
a DB whose tables already exist but whose `alembic_version` has no row
(the shape of any local `app.db` created before Alembic was adopted, by
the now-removed `Base.metadata.create_all()` startup safety net — see
that module's docstring for the full story).

Each test builds its own throwaway sqlite file and monkeypatches
`app.db.migrations.engine` + `settings.database_url` to point at it, so
these don't touch the real `app/data/app.db` and don't need the
import-time DATABASE_URL trick `test_auth.py` uses (this module talks
to its own `engine`/`Config` objects directly, never through the
already-constructed app-wide `app.db.session.engine` singleton).
"""

from __future__ import annotations

import os
import tempfile

import pytest
from sqlalchemy import create_engine, inspect

from app.db import migrations
from app.db.session import Base


def _sqlite_url(path: str) -> str:
    return "sqlite:///" + path.replace("\\", "/")


@pytest.fixture()
def temp_db_path(tmp_path):
    return str(tmp_path / "test.db")


@pytest.fixture()
def isolated_engine(temp_db_path, monkeypatch):
    """Point migrations.py's `engine` and the alembic config's target URL
    at a fresh temp sqlite file, restoring both after the test."""
    url = _sqlite_url(temp_db_path)
    test_engine = create_engine(url)
    monkeypatch.setattr(migrations, "engine", test_engine)
    monkeypatch.setattr(migrations.settings, "database_url", url)
    yield test_engine
    test_engine.dispose()


def _table_names(engine) -> set[str]:
    return set(inspect(engine).get_table_names())


def test_fresh_db_upgrades_normally(isolated_engine):
    """No tables at all -> the normal `upgrade head` path creates
    everything and records the head revision. This is the common case
    (a brand new checkout, or CI) and must not regress."""
    migrations.run_startup_migrations()

    tables = _table_names(isolated_engine)
    assert "users" in tables
    assert "sso_flows" in tables
    with isolated_engine.connect() as conn:
        rows = conn.exec_driver_sql("SELECT * FROM alembic_version").fetchall()
    assert len(rows) == 1


def test_pre_existing_tables_without_version_row_self_heals(isolated_engine):
    """The exact bug this module exists to fix: tables already exist
    (simulating the old create_all() safety net, or any DB that predates
    Alembic's adoption in this project), but `alembic_version` has no
    row. Must NOT raise `table ... already exists` — must stamp head
    instead, without touching the existing tables' data."""
    Base.metadata.create_all(bind=isolated_engine)
    assert "users" in _table_names(isolated_engine)
    # No alembic_version table at all yet — an even more literal reading
    # of "predates Alembic" than an empty one.
    assert "alembic_version" not in _table_names(isolated_engine)

    migrations.run_startup_migrations()  # must not raise

    with isolated_engine.connect() as conn:
        rows = conn.exec_driver_sql("SELECT * FROM alembic_version").fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "065a106ff3d7"


def test_pre_existing_tables_with_empty_version_table_self_heals(isolated_engine):
    """Same bug, slightly different shape: `alembic_version` exists as a
    table but has no row (e.g. a previous failed upgrade attempt left it
    behind empty). Must self-heal the same way."""
    Base.metadata.create_all(bind=isolated_engine)
    with isolated_engine.connect() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"
        )
        conn.commit()

    migrations.run_startup_migrations()  # must not raise

    with isolated_engine.connect() as conn:
        rows = conn.exec_driver_sql("SELECT * FROM alembic_version").fetchall()
    assert len(rows) == 1


def test_already_stamped_db_is_a_no_op(isolated_engine):
    """A DB that's already correctly at head must not be re-stamped or
    re-upgraded — running startup migrations twice in a row (the same
    thing happens on every `--reload` restart) must be a harmless no-op."""
    migrations.run_startup_migrations()
    with isolated_engine.connect() as conn:
        before = conn.exec_driver_sql("SELECT * FROM alembic_version").fetchall()

    migrations.run_startup_migrations()  # second call, must not raise
    with isolated_engine.connect() as conn:
        after = conn.exec_driver_sql("SELECT * FROM alembic_version").fetchall()

    assert before == after


def test_self_heal_does_not_touch_existing_row_data(isolated_engine):
    """The self-heal path must genuinely be a no-op on data — inserting a
    row before healing must find that exact row still there after."""
    Base.metadata.create_all(bind=isolated_engine)
    with isolated_engine.connect() as conn:
        conn.exec_driver_sql(
            "INSERT INTO users (id, email, hashed_password, role, created_at, auth_provider) "
            "VALUES ('u1', 'a@b.com', 'x', 'admin', '2026-01-01 00:00:00', 'local')"
        )
        conn.commit()

    migrations.run_startup_migrations()

    with isolated_engine.connect() as conn:
        rows = conn.exec_driver_sql("SELECT id, email FROM users").fetchall()
    assert rows == [("u1", "a@b.com")]
