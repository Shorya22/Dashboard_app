"""
Regression test: proves that uploading a dataset with new enum values
(regions, markets, departments, years/months/weeks) makes those values
automatically appear in filter dropdowns — with ZERO code or YAML
changes — and that rollback removes them again.

Follows the same pattern as `test_data_upload.py` (per-test isolated
upload storage + cache reset via `client` fixture).
"""

from __future__ import annotations

import io
import os
import tempfile

os.environ["DATABASE_URL"] = "sqlite:///" + tempfile.mktemp(
    prefix="dashboard_filter_refl_", suffix=".db"
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
REAL_BOOKING = DATA_DIR / "UTILIZATION DATA SHEET.xlsx"
XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_storage_dir", str(tmp_path / "uploads"))
    data_loader._roster_cache = None
    data_loader._booking_cache = None
    data_loader._booking_prepared_cache = None
    data_loader._utilization_ground_truth_cache = None
    limiter.reset()
    with TestClient(app) as c:
        yield c
    limiter.reset()
    data_loader._roster_cache = None
    data_loader._booking_cache = None
    data_loader._booking_prepared_cache = None
    data_loader._utilization_ground_truth_cache = None


def _admin_token(client) -> str:
    resp = client.post(
        "/api/auth/login", json={"email": SEED_EMAIL, "password": SEED_PASSWORD}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _xlsx_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, sheet_name="Sheet1", index=False)
    return buf.getvalue()


def _files(content: bytes, filename="upload.xlsx"):
    return {"file": (filename, content, XLSX_MEDIA)}


def _append_roster_rows(df: pd.DataFrame) -> pd.DataFrame:
    template = df.iloc[0].to_dict()
    extras = []
    for i, (region, market, dept, grade) in enumerate(
        [
            ("LATAM", "MEX", "Data Engineering", "P5"),
            ("LATAM", "MEX", "Data Engineering", "P4"),
            ("EMEA", "IBERIA", "Data Engineering", "P3"),
        ]
    ):
        row = dict(template)
        row["NEW_EMP_ID"] = f"SYN_TEST_{i+1}"
        row["EMP ID"] = f"SYN{i+1}"
        row["NAME"] = f"Synthetic Test {i+1}"
        row["Region"] = region
        row["Market"] = market
        row["Designation"] = dept
        row["GRADE"] = grade
        row["Type"] = "GCC"
        row["Status"] = "Active"
        extras.append(row)
    return pd.concat([df, pd.DataFrame(extras)], ignore_index=True)


def _append_booking_rows(df: pd.DataFrame) -> pd.DataFrame:
    template = df.iloc[0].to_dict()
    extras = []
    for region, market, dept, wk, day, emp in [
        ("LATAM", "MEX", "Data Engineering", "2027-01-04", "2027-01-04", "SYN_TEST_1"),
        ("LATAM", "MEX", "Data Engineering", "2027-01-04", "2027-01-05", "SYN_TEST_1"),
        ("LATAM", "MEX", "Data Engineering", "2027-01-04", "2027-01-06", "SYN_TEST_2"),
        ("EMEA", "IBERIA", "Data Engineering", "2027-01-04", "2027-01-04", "SYN_TEST_3"),
        ("EMEA", "IBERIA", "Data Engineering", "2027-01-04", "2027-01-05", "SYN_TEST_3"),
    ]:
        row = dict(template)
        row["Region (EC)"] = region
        row["Market (EC)"] = market
        row["Department"] = dept
        row["Monday of Week"] = pd.Timestamp(wk)
        row["Date"] = pd.Timestamp(day)
        row["Employee"] = emp
        row["Employee Booked Hours"] = 8.0
        row["Booked Hours Type"] = "Client Hours"
        if "Holding" in row:
            row["Holding"] = "SyntheticHolding"
        if "Project Name" in row:
            row["Project Name"] = "SyntheticProject"
        extras.append(row)
    return pd.concat([df, pd.DataFrame(extras)], ignore_index=True)


# --------------------------------------------------------------------- #
# roster reflection
# --------------------------------------------------------------------- #
def test_roster_new_values_reflected_in_filter_options(client):
    token = _admin_token(client)

    # Baseline: no LATAM / MEX / IBERIA / Data Engineering
    before = client.get(
        "/api/v1/utilization/filter-options", headers=_auth(token)
    ).json()
    assert "LATAM" not in before["regions"]
    assert "MEX" not in before["markets"]
    assert "IBERIA" not in before["markets"]
    assert "Data Engineering" not in before["departments"]

    # Snapshot config/filters shape for later comparison (definitions
    # must not be affected by data changes)
    cfg_before = client.get(
        "/api/v1/config/filters?dataset=roster", headers=_auth(token)
    ).json()

    # Upload roster + booking with synthetic rows
    r_df = _append_roster_rows(pd.read_excel(REAL_ROSTER))
    b_df = _append_booking_rows(pd.read_excel(REAL_BOOKING))
    r_resp = client.post(
        "/api/v1/data/upload/roster",
        files=_files(_xlsx_bytes(r_df)),
        headers=_auth(token),
    )
    assert r_resp.status_code == 200, r_resp.text
    assert r_resp.json()["status"] == "promoted"
    b_resp = client.post(
        "/api/v1/data/upload/booking",
        files=_files(_xlsx_bytes(b_df)),
        headers=_auth(token),
    )
    assert b_resp.status_code == 200, b_resp.text
    assert b_resp.json()["status"] == "promoted"

    # Filter-options now reflects new values
    after = client.get(
        "/api/v1/utilization/filter-options", headers=_auth(token)
    ).json()
    assert "LATAM" in after["regions"]
    assert "MEX" in after["markets"]
    assert "IBERIA" in after["markets"]
    assert "Data Engineering" in after["departments"]

    hierarchy = {h["region"]: set(h["markets"]) for h in after["region_market_hierarchy"]}
    assert "MEX" in hierarchy.get("LATAM", set())
    assert "IBERIA" in hierarchy.get("EMEA", set())

    years = {w["year"] for w in after["week_hierarchy"]}
    assert "2027" in years, f"expected 2027 in week_hierarchy, got {years}"

    # /config/filters shape is untouched — same keys, same labels, same nests
    cfg_after = client.get(
        "/api/v1/config/filters?dataset=roster", headers=_auth(token)
    ).json()
    assert cfg_before == cfg_after

    # Query-level filter respects the new value
    emp = client.get(
        "/api/v1/roster/employees?region=LATAM", headers=_auth(token)
    ).json()
    assert emp["total"] >= 2
    assert all(r["region"] == "LATAM" for r in emp["items"])

    summ = client.get(
        "/api/v1/utilization/summary?region=LATAM", headers=_auth(token)
    ).json()
    assert summ["total_hours"] > 0

    by_rm = client.get(
        "/api/v1/utilization/by-region-market?region=LATAM", headers=_auth(token)
    ).json()
    assert any(item["region"] == "LATAM" and item["market"] == "MEX"
               for item in by_rm["items"])


def test_rollback_removes_new_values_from_filter_options(client):
    token = _admin_token(client)

    # Establish baseline v1 (bundled/first-uploaded original)
    r_v1 = client.post(
        "/api/v1/data/upload/roster",
        files=_files(_xlsx_bytes(pd.read_excel(REAL_ROSTER))),
        headers=_auth(token),
    )
    assert r_v1.status_code == 200
    b_v1 = client.post(
        "/api/v1/data/upload/booking",
        files=_files(_xlsx_bytes(pd.read_excel(REAL_BOOKING))),
        headers=_auth(token),
    )
    assert b_v1.status_code == 200

    # Upload modified v2
    r_df = _append_roster_rows(pd.read_excel(REAL_ROSTER))
    b_df = _append_booking_rows(pd.read_excel(REAL_BOOKING))
    client.post(
        "/api/v1/data/upload/roster",
        files=_files(_xlsx_bytes(r_df)),
        headers=_auth(token),
    )
    client.post(
        "/api/v1/data/upload/booking",
        files=_files(_xlsx_bytes(b_df)),
        headers=_auth(token),
    )

    after = client.get(
        "/api/v1/utilization/filter-options", headers=_auth(token)
    ).json()
    assert "LATAM" in after["regions"]
    assert "2027" in {w["year"] for w in after["week_hierarchy"]}

    # Roll back both
    assert (
        client.post(
            "/api/v1/data/rollback/roster", headers=_auth(token)
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/data/rollback/booking", headers=_auth(token)
        ).status_code
        == 200
    )

    rolled = client.get(
        "/api/v1/utilization/filter-options", headers=_auth(token)
    ).json()
    assert "LATAM" not in rolled["regions"]
    assert "MEX" not in rolled["markets"]
    assert "IBERIA" not in rolled["markets"]
    assert "Data Engineering" not in rolled["departments"]
    assert "2027" not in {w["year"] for w in rolled["week_hierarchy"]}
