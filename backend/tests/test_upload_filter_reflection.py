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


# --------------------------------------------------------------------- #
# Search / Results — end-to-end upload-reflection regression
# --------------------------------------------------------------------- #
# Locks that uploading a booking file with a new Holding + Entity + Region
# / Market surfaces immediately in the Utilization Search page's filter
# dropdowns AND in the Results page's KPI strip + records table, with no
# code or YAML changes. Mirrors the roster reflection test above but
# targets the Search -> Results flow the coordinator just extended.
def test_search_results_reflect_new_booking_data(client):
    token = _admin_token(client)

    # Baseline: none of these synthetic values appear yet.
    before = client.get(
        "/api/v1/utilization/filter-options", headers=_auth(token)
    ).json()
    assert "SyntheticHolding" not in before["holdings"]
    assert "LATAM" not in before["regions"]

    # Upload the modified booking sheet (adds LATAM/MEX rows tied to a
    # synthetic holding + employees).
    r_df = _append_roster_rows(pd.read_excel(REAL_ROSTER))
    b_df = _append_booking_rows(pd.read_excel(REAL_BOOKING))
    assert (
        client.post(
            "/api/v1/data/upload/roster",
            files=_files(_xlsx_bytes(r_df)),
            headers=_auth(token),
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/data/upload/booking",
            files=_files(_xlsx_bytes(b_df)),
            headers=_auth(token),
        ).status_code
        == 200
    )

    # (1) Search filter dropdowns now show the new holding + region.
    after = client.get(
        "/api/v1/utilization/filter-options", headers=_auth(token)
    ).json()
    assert "SyntheticHolding" in after["holdings"]
    assert "LATAM" in after["regions"]

    # (2) Results endpoint (`/utilization/records`) — filtering by the
    # new holding returns the synthetic rows AND the KPI strip's Total
    # Hours + Average Hours reflect them (the summary must route through
    # the config-driven cards, matching the
    # `records_summary_reuses_declared_cards` invariant).
    resp = client.get(
        "/api/v1/utilization/records?holding=SyntheticHolding",
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # 5 synthetic rows, 8.0h each -> 40h total, 8h mean.
    assert body["total"] == 5
    assert body["summary"]["total_hours"] == pytest.approx(40.0)
    assert body["summary"]["client_hours"] == pytest.approx(40.0)  # all Client Hours
    assert body["summary"]["internal_hours"] == pytest.approx(0.0)
    assert body["summary"]["average_hours"] == pytest.approx(8.0)
    # SyntheticProject was the only project row for this holding.
    assert body["summary"]["total_projects"] == 1
    # Every returned record must belong to the synthetic holding.
    assert all(item["holding"] == "SyntheticHolding" for item in body["items"])

    # (3) The Search-page holdings-projects hierarchy also reflects it.
    hp = client.get(
        "/api/v1/utilization/holdings-projects", headers=_auth(token)
    ).json()
    holdings = {h["holding"]: h["projects"] for h in hp["items"]}
    assert "SyntheticProject" in holdings.get("SyntheticHolding", [])

    # (4) Employee filter (added 2026-07-24) — every synthetic employee
    # from the newly-uploaded booking appears in the dropdown, and
    # filtering /records by one narrows to that employee's rows.
    employees = after["employees"]
    assert "SYN_TEST_1" in employees
    assert "SYN_TEST_3" in employees
    filtered = client.get(
        "/api/v1/utilization/records?employee=SYN_TEST_1",
        headers=_auth(token),
    ).json()
    # SYN_TEST_1 booked 2 rows above; other synthetic employees excluded.
    assert filtered["total"] == 2
    assert all(item["employee"] == "SYN_TEST_1" for item in filtered["items"])


# --------------------------------------------------------------------- #
# Booking-only Employee — locking test for cross-dataset SOFT warning
# --------------------------------------------------------------------- #
# Coordinator decision (2026-07-23): the roster-vs-booking count gap is a
# WARNING, never a blocker — a booking upload can legitimately arrive
# before the corresponding roster refresh. This test locks that contract:
# a booking upload with an Employee not present in the current roster
# must (1) commit, (2) surface exactly the `unmatched_in_roster` warning,
# and (3) produce zero ERROR-severity issues.
def test_booking_only_employee_warns_but_does_not_block_upload(client):
    token = _admin_token(client)

    # Establish the real roster as the baseline (so "booking-only" is a
    # meaningful comparison — an Employee this roster does not contain).
    r_resp = client.post(
        "/api/v1/data/upload/roster",
        files=_files(_xlsx_bytes(pd.read_excel(REAL_ROSTER))),
        headers=_auth(token),
    )
    assert r_resp.status_code == 200
    assert r_resp.json()["status"] == "promoted"

    # Booking upload with one row whose Employee is deliberately NOT in
    # the roster (single-token name that cannot subset-match any real
    # roster row — the token-subset matcher in cross_dataset.py accepts
    # any subset relation, so a totally unique token is the safest
    # guarantee of "unmatched").
    b_df = pd.read_excel(REAL_BOOKING)
    ghost_row = b_df.iloc[0].to_dict()
    ghost_row["Employee"] = "Zzzghostemployee Xyzzy"
    ghost_row["Employee Booked Hours"] = 4.0
    ghost_row["Booked Hours Type"] = "Client Hours"
    b_df = pd.concat([b_df, pd.DataFrame([ghost_row])], ignore_index=True)

    b_resp = client.post(
        "/api/v1/data/upload/booking",
        files=_files(_xlsx_bytes(b_df)),
        headers=_auth(token),
    )
    # (1) upload committed — never blocked.
    assert b_resp.status_code == 200, b_resp.text
    body = b_resp.json()
    assert body["status"] == "promoted"
    report = body["report"]

    # (3) zero ERROR-severity issues.
    assert report["error_count"] == 0, report["issues"]

    # (2) exactly one `unmatched_in_roster` warning naming our ghost.
    ghost_warnings = [
        i for i in report["issues"]
        if i["severity"] == "warning"
        and i["rule"] == "unmatched_in_roster"
        and i.get("value") == "Zzzghostemployee Xyzzy"
    ]
    assert len(ghost_warnings) == 1, ghost_warnings
