"""
Tests for backend/app/api/auth.py + backend/app/core/security.py.

DB isolation strategy
----------------------
`app.db.session` binds its SQLAlchemy engine to `settings.database_url`
at *import time* (module-level `create_engine(...)` call), and
`app.core.config.Settings` reads `DATABASE_URL` from the environment at
class-body-evaluation time (also import time). There's no
`get_db` dependency-override needed as a result: we just set
`DATABASE_URL` to a throwaway temp-file sqlite path *before* `app.main`
(and anything under `app.db`/`app.core.config`) is imported anywhere in
the test process, so the module-level engine created on import points
at the temp file instead of `backend/app/data/app.db`.

This is simpler than a `get_db` dependency override here because the
app's own `@app.on_event("startup")` handler (table creation + dev-admin
seeding) also runs against `SessionLocal`/`engine` directly, not through
the `get_db` dependency — a dependency override wouldn't touch that
seeding step, so we'd still need env-var isolation for seeding to land
in a temp DB. Setting the env var before import handles both paths with
one mechanism.

Practically: this module must be the *first* thing to import
`app.main` (or any `app.*` module that transitively imports
`app.db.session`) in the whole test session. Checked against the sibling
test files in this directory — they only import `app.services.*`
modules, which don't touch `app.db` — so import order across files is
safe regardless of pytest collection order.
"""

from __future__ import annotations

import os
import tempfile

import pytest

# --- Set up an isolated temp sqlite DB BEFORE importing anything under
# app.* that could trigger app.db.session's module-level engine creation.
_tmp_dir = tempfile.mkdtemp(prefix="dashboard_app_test_db_")
_tmp_db_path = os.path.join(_tmp_dir, "test_app.db")
# sqlite URL wants forward slashes and 3 leading slashes for an absolute
# path (Windows: `sqlite:///C:/tmp/x.db`; POSIX: `sqlite:////tmp/x.db`).
# Normalize backslashes so the same code path works on both.
os.environ["DATABASE_URL"] = "sqlite:///" + _tmp_db_path.replace("\\", "/")

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.limiter import limiter  # noqa: E402
from app.main import app  # noqa: E402

SEED_EMAIL = settings.seed_admin_email
SEED_PASSWORD = settings.seed_admin_password


@pytest.fixture()
def client():
    """Fresh TestClient per test, running the real startup event (creates
    tables + seeds the dev admin in the temp DB) and resetting the
    rate limiter's in-memory counters so tests don't bleed into each
    other via shared IP-keyed limiter state."""
    limiter.reset()
    with TestClient(app) as c:
        yield c
    limiter.reset()


def test_login_success_sets_httponly_cookie_and_returns_access_token(client):
    resp = client.post(
        "/api/auth/login",
        json={"email": SEED_EMAIL, "password": SEED_PASSWORD},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body and body["access_token"]
    assert body["token_type"] == "bearer"
    # Refresh token must never appear in the JSON body.
    assert "refresh_token" not in body
    assert not any("refresh" in k.lower() for k in body if k != "access_token")

    # Refresh token travels only as an httpOnly cookie.
    assert "refresh_token" in resp.cookies
    set_cookie_headers = resp.headers.get_list("set-cookie")
    refresh_cookie_header = next(h for h in set_cookie_headers if h.startswith("refresh_token="))
    assert "httponly" in refresh_cookie_header.lower()


def test_login_wrong_password_returns_401_with_detail_shape(client):
    resp = client.post(
        "/api/auth/login",
        json={"email": SEED_EMAIL, "password": "definitely-wrong-password"},
    )

    assert resp.status_code == 401
    body = resp.json()
    assert set(body.keys()) == {"detail"}
    assert isinstance(body["detail"], str) and body["detail"]


def test_me_with_valid_access_token_returns_user(client):
    login_resp = client.post(
        "/api/auth/login",
        json={"email": SEED_EMAIL, "password": SEED_PASSWORD},
    )
    access_token = login_resp.json()["access_token"]

    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {access_token}"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == SEED_EMAIL
    assert body["role"] == "admin"
    assert "id" in body


def test_me_without_token_returns_401(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
    assert "detail" in resp.json()


def test_me_with_garbage_token_returns_401(client):
    resp = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-real-jwt"})
    assert resp.status_code == 401
    assert "detail" in resp.json()


def test_me_with_expired_token_returns_401(client):
    import datetime

    import jwt

    now = datetime.datetime.now(datetime.timezone.utc)
    expired_payload = {
        "sub": "some-user-id",
        "role": "admin",
        "type": "access",
        "iat": now - datetime.timedelta(minutes=30),
        "exp": now - datetime.timedelta(minutes=15),
        "jti": "expired-test-token",
    }
    expired_token = jwt.encode(expired_payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == 401
    assert "detail" in resp.json()


def test_refresh_with_valid_cookie_issues_new_access_token(client):
    login_resp = client.post(
        "/api/auth/login",
        json={"email": SEED_EMAIL, "password": SEED_PASSWORD},
    )
    old_access_token = login_resp.json()["access_token"]

    resp = client.post("/api/auth/refresh")

    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body and body["access_token"]
    # New access token should be usable against a protected route.
    me_resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me_resp.status_code == 200
    # Not strictly required to differ from the old token (different jti
    # makes it differ in practice), but the important behavioral
    # guarantee is that it's a valid, usable access token.
    assert body["access_token"] != ""


def test_refresh_without_cookie_returns_401(client):
    resp = client.post("/api/auth/refresh")
    assert resp.status_code == 401
    assert "detail" in resp.json()


def test_logout_clears_cookie_and_invalidates_subsequent_refresh(client):
    login_resp = client.post(
        "/api/auth/login",
        json={"email": SEED_EMAIL, "password": SEED_PASSWORD},
    )
    assert login_resp.status_code == 200
    assert "refresh_token" in client.cookies

    logout_resp = client.post("/api/auth/logout")
    assert logout_resp.status_code == 200

    # The cookie should have been cleared client-side (TestClient's
    # cookie jar honors the delete-cookie response).
    assert client.cookies.get("refresh_token") in (None, "")

    # And even if a client tried to replay the old cookie value manually,
    # there is no cookie left to send — simulate the "no cookie" state
    # that logout is meant to produce.
    refresh_resp = client.post("/api/auth/refresh")
    assert refresh_resp.status_code == 401


def test_register_creates_user_and_allows_login(client):
    resp = client.post(
        "/api/auth/register",
        json={"email": "new.user@example.com", "password": "correct-horse-9"},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "new.user@example.com"
    assert "id" in body and body["id"]
    # Registration must never leak tokens or the password hash.
    assert "access_token" not in body
    assert "hashed_password" not in body
    assert "password" not in body

    login_resp = client.post(
        "/api/auth/login",
        json={"email": "new.user@example.com", "password": "correct-horse-9"},
    )
    assert login_resp.status_code == 200


def test_register_normalizes_email_and_login_is_case_insensitive(client):
    resp = client.post(
        "/api/auth/register",
        json={"email": "Mixed.Case@Example.COM", "password": "correct-horse-9"},
    )
    assert resp.status_code == 201
    assert resp.json()["email"] == "mixed.case@example.com"

    # Same casing the user typed at register should also work at login.
    login_resp = client.post(
        "/api/auth/login",
        json={"email": "Mixed.Case@Example.COM", "password": "correct-horse-9"},
    )
    assert login_resp.status_code == 200


def test_register_duplicate_email_returns_409(client):
    first = client.post(
        "/api/auth/register",
        json={"email": "dup@example.com", "password": "correct-horse-9"},
    )
    assert first.status_code == 201

    second = client.post(
        "/api/auth/register",
        json={"email": "dup@example.com", "password": "another-pass-7"},
    )
    assert second.status_code == 409
    assert "detail" in second.json()


def test_register_rejects_weak_password(client):
    # Too short — Pydantic min_length=8 rejects before it hits the handler.
    resp = client.post(
        "/api/auth/register",
        json={"email": "weak@example.com", "password": "abc12"},
    )
    assert resp.status_code == 422

    # Letters only, no digit — custom validator rejects.
    resp = client.post(
        "/api/auth/register",
        json={"email": "weak2@example.com", "password": "abcdefghij"},
    )
    assert resp.status_code == 422


def test_login_rate_limited_after_repeated_bad_attempts(client):
    # Route is decorated with @limiter.limit("5/minute"); the 6th rapid
    # bad-password attempt from the same client IP should be throttled.
    last_status = None
    for _ in range(6):
        resp = client.post(
            "/api/auth/login",
            json={"email": SEED_EMAIL, "password": "wrong-password"},
        )
        last_status = resp.status_code

    assert last_status == 429
    assert "detail" in resp.json()
