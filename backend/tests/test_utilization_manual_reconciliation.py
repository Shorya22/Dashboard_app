"""
Task 3 (2026-07-26) — end-to-end manual reconciliation of every utilization
number against the currently active booking data, computed independently
with pandas and compared to the live HTTP endpoints. Locks in the
zero-discrepancy result found during that review as a permanent regression
test (a future code change that silently breaks one of these numbers will
fail here, not just in an ad hoc script).

Groups covered, matching the manual validation tables in the Task 3
report/commit body:
1. Utilization Home KPI strip
2. Search/Results summary for two real filter combos (region, holding)
3. Overview (Formula A): Average Period / Latest Week Utilization %,
   Utilization Split band counts
4. Employee Utilization drill-through, for 3 real employees
5. Project (Holding) Utilization drill-through, for 3 real holdings
   (also confirms Total Employees != Total Projects on the current v4
   data — the earlier "49/49 coincidence" no longer holds now that
   Total Projects is 81, not 49)
"""

from __future__ import annotations

import math

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services import data_loader

SEED_EMAIL = settings.seed_admin_email
SEED_PASSWORD = settings.seed_admin_password


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def auth_headers(client):
    resp = client.post(
        "/api/auth/login", json={"email": SEED_EMAIL, "password": SEED_PASSWORD}
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def booking_df():
    data_loader.reload_booking_data()
    return data_loader.get_booking_df_prepared()


def _approx(a, b, tol=1e-3):
    return math.isclose(float(a), float(b), abs_tol=tol)


def _ratio(g):
    c = g.loc[g["Booked Hours Type"] == "Client Hours", "Employee Booked Hours"].sum()
    i = g.loc[g["Booked Hours Type"] == "Internal Hours", "Employee Booked Hours"].sum()
    total = c + i
    return c / total if total > 0 else float("nan")


def test_utilization_home_summary_reconciles(client, auth_headers, booking_df):
    df = booking_df
    manual = dict(
        total_employees=df["Employee"].nunique(),
        total_hours=df["Employee Booked Hours"].sum(),
        client_hours=df.loc[df["Booked Hours Type"] == "Client Hours", "Employee Booked Hours"].sum(),
        internal_hours=df.loc[df["Booked Hours Type"] == "Internal Hours", "Employee Booked Hours"].sum(),
        total_projects=df["Project Name"].dropna().nunique(),
    )
    body = client.get("/api/v1/utilization/summary", headers=auth_headers).json()
    for key, value in manual.items():
        assert _approx(value, body[key]), f"{key}: manual={value} endpoint={body[key]}"


@pytest.mark.parametrize("filter_key", ["region", "holding"])
def test_search_results_summary_reconciles_for_a_real_value(
    client, auth_headers, booking_df, filter_key
):
    df = booking_df
    column = {"region": "Region (EC)", "holding": "Holding"}[filter_key]
    value = df[column].dropna().unique()[0]
    sub = df[df[column] == value]
    manual = dict(
        total_hours=sub["Employee Booked Hours"].sum(),
        client_hours=sub.loc[sub["Booked Hours Type"] == "Client Hours", "Employee Booked Hours"].sum(),
        internal_hours=sub.loc[sub["Booked Hours Type"] == "Internal Hours", "Employee Booked Hours"].sum(),
        total_projects=sub["Project Name"].dropna().nunique(),
        average_hours=sub["Employee Booked Hours"].mean(),
    )
    resp = client.get(
        f"/api/v1/utilization/records?{filter_key}={value}", headers=auth_headers
    ).json()
    summary = resp["summary"]
    for key, expected in manual.items():
        assert _approx(expected, summary[key]), f"{key}: manual={expected} endpoint={summary[key]}"


def test_overview_formula_a_reconciles(client, auth_headers, booking_df):
    df = booking_df
    emp_period = df.groupby("Employee").apply(_ratio, include_groups=False).dropna()
    avg_period = emp_period.mean()

    latest_week = df["Monday of Week"].max()
    latest_ratio = (
        df[df["Monday of Week"] == latest_week]
        .groupby("Employee")
        .apply(_ratio, include_groups=False)
        .dropna()
        .mean()
    )

    def band(v):
        if v >= 0.9:
            return "high"
        if v >= 0.8:
            return "moderate"
        return "low"

    manual_split = emp_period.apply(band).value_counts().to_dict()

    body = client.get("/api/v1/utilization/overview", headers=auth_headers).json()
    assert _approx(avg_period, body["average_period_utilization_pct"], tol=1e-6)
    assert _approx(latest_ratio, body["latest_week_utilization_pct"], tol=1e-6)
    for band_name in ("high", "moderate", "low"):
        assert manual_split.get(band_name, 0) == body["utilization_split"].get(band_name, 0)


def test_employee_drill_through_reconciles_for_real_employees(client, auth_headers, booking_df):
    df = booking_df
    for employee in df["Employee"].dropna().unique()[:3]:
        sub = df[df["Employee"] == employee]
        manual = dict(
            total_hours=sub["Employee Booked Hours"].sum(),
            client_hours=sub.loc[sub["Booked Hours Type"] == "Client Hours", "Employee Booked Hours"].sum(),
            internal_hours=sub.loc[sub["Booked Hours Type"] == "Internal Hours", "Employee Booked Hours"].sum(),
            total_projects=sub["Project Name"].dropna().nunique(),
        )
        body = client.get(f"/api/v1/utilization/employees/{employee}", headers=auth_headers).json()
        for key, expected in manual.items():
            assert _approx(expected, body[key]), f"{employee}.{key}: manual={expected} endpoint={body[key]}"


def test_project_drill_through_reconciles_for_real_holdings(client, auth_headers, booking_df):
    df = booking_df
    total_employees_home = df["Employee"].nunique()
    total_projects_home = df["Project Name"].dropna().nunique()
    # Confirmed change on v4: Total Employees (49) != Total Projects (81) —
    # the earlier "49/49 coincidence" documented for a prior snapshot no
    # longer holds now that the active booking data has 81 distinct
    # Project Name values.
    assert total_employees_home != total_projects_home

    for holding in df["Holding"].dropna().unique()[:3]:
        sub = df[df["Holding"] == holding]
        manual = dict(
            total_hours=sub["Employee Booked Hours"].sum(),
            client_hours=sub.loc[sub["Booked Hours Type"] == "Client Hours", "Employee Booked Hours"].sum(),
            internal_hours=sub.loc[sub["Booked Hours Type"] == "Internal Hours", "Employee Booked Hours"].sum(),
        )
        distinct_employees = sub["Employee"].dropna().nunique()
        body = client.get(f"/api/v1/utilization/projects/{holding}", headers=auth_headers).json()
        for key, expected in manual.items():
            assert _approx(expected, body[key]), f"{holding}.{key}: manual={expected} endpoint={body[key]}"
        # Total Employees for a holding isn't a declared card in the API
        # response today (see METRICS.md Page 10 — computed client-side
        # from the paginated records feed); assert the manual figure is
        # at least sane (non-zero, <= total booking employees).
        assert 0 < distinct_employees <= total_employees_home
