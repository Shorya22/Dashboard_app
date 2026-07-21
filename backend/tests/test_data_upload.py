"""
Integration tests for the Phase 8b data-upload API.

Covers auth gating (admin vs viewer), the full upload lifecycle (validate
dry-run, promote, fingerprint dedup, reject-without-touching-active,
rollback), and the schema/template/history/status endpoints.

DB isolation follows the same env-var-before-import pattern documented in
test_auth.py. Storage is isolated per test via a fresh temp dir and by
resetting data_loader's in-memory caches so uploads in one test never
bleed into another.
"""

from __future__ import annotations

import io
import os
import tempfile

os.environ["DATABASE_URL"] = "sqlite:///" + tempfile.mktemp(
    prefix="dashboard_upload_test_", suffix=".db"
).replace("\\", "/")

from pathlib import Path  # noqa: E402

import pandas as pd  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.limiter import limiter  # noqa: E402
from app.main import app  # noqa: E402
from app.services import data_loader  # noqa: E402

SEED_EMAIL = settings.seed_admin_email
SEED_PASSWORD = settings.seed_admin_password
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
REAL_ROSTER = DATA_DIR / "DEPT - Master Data(Sheet1).xlsx"
XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Client with an isolated per-test upload storage dir + fresh caches."""
    monkeypatch.setattr(settings, "upload_storage_dir", str(tmp_path / "uploads"))
    # Clear cached DataFrames so each test starts from the bundled default.
    data_loader._roster_cache = None
    data_loader._booking_cache = None
    data_loader._booking_prepared_cache = None
    data_loader._utilization_ground_truth_cache = None
    limiter.reset()
    with TestClient(app) as c:
        yield c
    limiter.reset()
    # Reset caches on teardown too, so a DataFrame loaded from this test's
    # temp storage can never leak into a later-running test module.
    data_loader._roster_cache = None
    data_loader._booking_cache = None
    data_loader._booking_prepared_cache = None
    data_loader._utilization_ground_truth_cache = None


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _admin_token(client) -> str:
    resp = client.post(
        "/api/auth/login", json={"email": SEED_EMAIL, "password": SEED_PASSWORD}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _viewer_token(client, email="viewer@example.com") -> str:
    client.post("/api/auth/register", json={"email": email, "password": "viewer-pass-9"})
    resp = client.post("/api/auth/login", json={"email": email, "password": "viewer-pass-9"})
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _xlsx_bytes(df: pd.DataFrame, sheet_name="Sheet1") -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, sheet_name=sheet_name, index=False)
    return buf.getvalue()


def _real_roster_bytes() -> bytes:
    return REAL_ROSTER.read_bytes()


def _files(content: bytes, filename="roster.xlsx"):
    return {"file": (filename, content, XLSX_MEDIA)}


# --------------------------------------------------------------------------- #
# auth gating
# --------------------------------------------------------------------------- #
def test_upload_requires_auth(client):
    resp = client.post("/api/v1/data/upload/roster", files=_files(_real_roster_bytes()))
    assert resp.status_code == 401


def test_upload_forbidden_for_viewer(client):
    token = _viewer_token(client)
    resp = client.post(
        "/api/v1/data/upload/roster",
        files=_files(_real_roster_bytes()),
        headers=_auth(token),
    )
    assert resp.status_code == 403


def test_unknown_file_type_404(client):
    token = _admin_token(client)
    resp = client.post(
        "/api/v1/data/upload/not_a_dataset",
        files=_files(_real_roster_bytes()),
        headers=_auth(token),
    )
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# validate (dry run)
# --------------------------------------------------------------------------- #
def test_validate_good_file_passes_and_stores_nothing(client):
    token = _admin_token(client)
    resp = client.post(
        "/api/v1/data/validate/roster",
        files=_files(_real_roster_bytes()),
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["passed"] is True
    assert body["error_count"] == 0
    # dry run promotes nothing
    hist = client.get("/api/v1/data/history/roster", headers=_auth(token)).json()
    assert hist["active_version"] is None


def test_validate_bad_file_reports_errors(client):
    token = _admin_token(client)
    df = pd.read_excel(REAL_ROSTER)
    df.loc[0, "Status"] = "Retired"  # system-fixed enum -> hard error
    resp = client.post(
        "/api/v1/data/validate/roster",
        files=_files(_xlsx_bytes(df)),
        headers=_auth(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["passed"] is False
    assert any(i["column"] == "Status" for i in body["issues"])


# --------------------------------------------------------------------------- #
# upload lifecycle
# --------------------------------------------------------------------------- #
def test_upload_promotes_and_updates_live_data(client):
    token = _admin_token(client)
    df = pd.read_excel(REAL_ROSTER)
    df.loc[0, "NAME"] = "Uploaded Person One"
    resp = client.post(
        "/api/v1/data/upload/roster",
        files=_files(_xlsx_bytes(df)),
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "promoted"
    assert body["version"] == 1
    # live dashboard endpoint reflects the new data
    summary = client.get("/api/v1/roster/summary", headers=_auth(token))
    assert summary.status_code == 200
    assert data_loader.get_roster_df().loc[0, "NAME"] == "Uploaded Person One"


def test_upload_rejects_bad_file_with_422_and_keeps_active_unchanged(client):
    token = _admin_token(client)
    # first, a good upload -> v1
    client.post(
        "/api/v1/data/upload/roster",
        files=_files(_real_roster_bytes()),
        headers=_auth(token),
    )
    # then a broken one
    df = pd.read_excel(REAL_ROSTER)
    df.loc[0, "Total Experience"] = df.loc[0, "Total Experience"] + 99
    resp = client.post(
        "/api/v1/data/upload/roster",
        files=_files(_xlsx_bytes(df)),
        headers=_auth(token),
    )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["status"] == "rejected"
    assert detail["report"]["error_count"] >= 1
    # active version unchanged
    hist = client.get("/api/v1/data/history/roster", headers=_auth(token)).json()
    assert hist["active_version"] == 1


def test_upload_duplicate_is_noop(client):
    token = _admin_token(client)
    content = _real_roster_bytes()
    r1 = client.post(
        "/api/v1/data/upload/roster", files=_files(content), headers=_auth(token)
    )
    assert r1.json()["status"] == "promoted"
    r2 = client.post(
        "/api/v1/data/upload/roster", files=_files(content), headers=_auth(token)
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "duplicate"
    assert r2.json()["version"] == 1


def test_rollback_restores_previous_version(client):
    token = _admin_token(client)
    # v1
    client.post(
        "/api/v1/data/upload/roster",
        files=_files(_real_roster_bytes()),
        headers=_auth(token),
    )
    # v2 (modified)
    df = pd.read_excel(REAL_ROSTER)
    df.loc[0, "NAME"] = "Version Two Person"
    client.post(
        "/api/v1/data/upload/roster",
        files=_files(_xlsx_bytes(df)),
        headers=_auth(token),
    )
    assert data_loader.get_roster_df().loc[0, "NAME"] == "Version Two Person"
    # rollback -> v1
    resp = client.post("/api/v1/data/rollback/roster", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["active_version"] == 1
    assert data_loader.get_roster_df().loc[0, "NAME"] != "Version Two Person"


def test_rollback_with_no_history_returns_409(client):
    token = _admin_token(client)
    resp = client.post("/api/v1/data/rollback/roster", headers=_auth(token))
    assert resp.status_code == 409


# --------------------------------------------------------------------------- #
# schema / template / status
# --------------------------------------------------------------------------- #
def test_schema_endpoint_serializes_contract(client):
    token = _admin_token(client)
    resp = client.get("/api/v1/data/schema/roster", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["file_type"] == "roster"
    grade = next(c for c in body["columns"] if c["name"] == "GRADE")
    assert "Grade TBD" in grade["allowed_values"]
    assert any(r["name"] == "total_experience_sum" for r in body["business_rules"])


def test_template_download_has_expected_columns(client):
    token = _admin_token(client)
    resp = client.get("/api/v1/data/template/roster", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.headers["content-type"] == XLSX_MEDIA
    df = pd.read_excel(io.BytesIO(resp.content))
    assert "NEW_EMP_ID" in df.columns
    assert len(df) == 0  # blank template


def test_status_lists_all_datasets(client):
    token = _admin_token(client)
    resp = client.get("/api/v1/data/status", headers=_auth(token))
    assert resp.status_code == 200
    datasets = {d["file_type"]: d for d in resp.json()["datasets"]}
    assert set(datasets) == {"roster", "booking", "ground_truth"}
    assert datasets["roster"]["source"] == "default"  # nothing uploaded yet


def test_report_download_after_upload(client):
    token = _admin_token(client)
    client.post(
        "/api/v1/data/upload/roster",
        files=_files(_real_roster_bytes()),
        headers=_auth(token),
    )
    resp = client.get("/api/v1/data/report/roster/1", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.headers["content-type"] == XLSX_MEDIA
