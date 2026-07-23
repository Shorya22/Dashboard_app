"""HTTP-level regression tests for filter-aware Utilization endpoints.

Locks in Phase 1 Bug B fix: `/utilization/summary`, `/weekly-trend`,
`/by-region`, and `/by-region-market` all accept the same repeated
query-param filters as `/utilization/records`, so every chart / KPI on
Utilization Home reacts to the filter row identically. Previously these
four returned unfiltered aggregates and the Total Hours by Region /
Market chart stayed the same no matter which region the user picked.
"""

from __future__ import annotations

from tests.test_auth import client, SEED_EMAIL, SEED_PASSWORD  # noqa: F401


def _auth_headers(client) -> dict[str, str]:  # noqa: F811
    resp = client.post(
        "/api/auth/login",
        json={"email": SEED_EMAIL, "password": SEED_PASSWORD},
    )
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_by_region_market_no_filters_is_full_dataset(client):  # noqa: F811
    resp = client.get("/api/v1/utilization/by-region-market", headers=_auth_headers(client))
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    unfiltered_regions = {r["region"] for r in body["items"]}
    # The real booking sheet's Region (EC) has both AMER and EMEA.
    assert unfiltered_regions.issuperset({"AMER", "EMEA"})


def test_by_region_market_narrows_by_region_param(client):  # noqa: F811
    """A `?region=AMER` query narrows the chart to AMER-only rows."""
    resp = client.get(
        "/api/v1/utilization/by-region-market?region=AMER",
        headers=_auth_headers(client),
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    # Every returned row must be in AMER — the chart no longer ignores the filter.
    assert items, "expected at least one AMER row"
    assert all(r["region"] == "AMER" for r in items)


def test_by_region_market_empty_when_filter_excludes_everything(client):  # noqa: F811
    """A region that exists in the roster but not in booking narrows to 0
    rows. The chart shows an honest empty rather than the full dataset."""
    resp = client.get(
        "/api/v1/utilization/by-region-market?region=APAC",
        headers=_auth_headers(client),
    )
    assert resp.status_code == 200
    assert resp.json()["items"] == []


def test_summary_narrows_by_region_param(client):  # noqa: F811
    """`/utilization/summary` (the Utilization Home KPIs) must respect the
    same Region filter — previously it returned the unfiltered totals."""
    full = client.get(
        "/api/v1/utilization/summary",
        headers=_auth_headers(client),
    ).json()
    narrowed = client.get(
        "/api/v1/utilization/summary?region=AMER",
        headers=_auth_headers(client),
    ).json()
    # Narrowing to a single region can only shrink each of these totals.
    assert narrowed["total_hours"] <= full["total_hours"]
    assert narrowed["client_hours"] <= full["client_hours"]
    assert narrowed["internal_hours"] <= full["internal_hours"]
    # Total Hours must strictly change when only some rows are in AMER — this
    # is the concrete Utilization Home KPI bug locking-in test.
    assert narrowed["total_hours"] < full["total_hours"]


def test_by_region_narrows_by_market_param(client):  # noqa: F811
    """`/utilization/by-region` accepts the shared filter dep too — cross-field
    ANDing is inherited from `get_filtered_records`."""
    resp = client.get(
        "/api/v1/utilization/by-region?market=UKI",
        headers=_auth_headers(client),
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    # UKI is an EMEA market; the result should be EMEA-only.
    if items:
        assert all(r["region"] == "EMEA" for r in items)
