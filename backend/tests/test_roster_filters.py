"""
End-to-end validation of the page filters (Home / HR Home / HR Analytics /
Workforce / Skills & Experience / Employee Directory).

Two layers:

1. Data-integration tests over the REAL bundled roster — for every filter
   declared in configs/roster_metrics.yaml, every dropdown value a page can
   offer must actually narrow the data to only matching rows, and the
   single-value filters must PARTITION the roster (each row lands in exactly
   one bucket, so the option counts sum to the row total). This is the guard
   against the class of bug where a filter silently returns 0 rows because the
   value the UI sends never matches the raw column (e.g. a re-normalised label).

2. An API guard — the /roster endpoints accept exactly the declared filters,
   read generically from the config, so adding/removing a filter in YAML can
   never drift from what the HTTP layer accepts.

DB isolation follows the same env-var-before-import pattern as
test_data_upload.py / test_auth.py.
"""

from __future__ import annotations

import os
import tempfile

os.environ["DATABASE_URL"] = "sqlite:///" + tempfile.mktemp(
    prefix="dashboard_filter_test_", suffix=".db"
).replace("\\", "/")

import pandas as pd  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.services import metric_config, roster_metrics  # noqa: E402
from app.services.data_loader import get_roster_df  # noqa: E402

SEED_EMAIL = settings.seed_admin_email
SEED_PASSWORD = settings.seed_admin_password


@pytest.fixture(scope="module")
def roster() -> pd.DataFrame:
    return get_roster_df()


def _server_filters() -> dict[str, dict]:
    """Every filter that actually runs through `apply_filters` — client-only
    filters (e.g. Month/Year narrowing the trend arrays in the browser)
    have no server-side row-filter behavior and are excluded from tests
    that iterate the roster."""
    return {
        name: spec
        for name, spec in metric_config.filters().items()
        if not spec.get("client_only")
    }


def _column_filters() -> list[str]:
    """Declared filters backed by a single column (excludes derived ones)."""
    return [
        name
        for name, spec in _server_filters().items()
        if "derived_from_chart" not in spec
    ]


def _derived_filters() -> list[str]:
    return [
        name
        for name, spec in _server_filters().items()
        if "derived_from_chart" in spec
    ]


def _option_values(df: pd.DataFrame, name: str, spec: dict) -> list[str]:
    """The dropdown values a page can offer for this filter, mirroring the
    frontend: raw distinct column values, or chart bucket labels for derived
    filters."""
    chart = spec.get("derived_from_chart")
    if chart:
        labels = roster_metrics.chart_labels(df, metric_config.chart(chart))
        return sorted(labels.astype(str).unique())
    column = metric_config.column(spec["column_role"])
    return sorted(df[column].dropna().astype(str).unique())


# --------------------------------------------------------------------------- #
# 1. Every option of every filter narrows to only matching rows
# --------------------------------------------------------------------------- #
def test_every_filter_option_returns_only_matching_rows(roster):
    for name, spec in _server_filters().items():
        chart = spec.get("derived_from_chart")
        column = None if chart else metric_config.column(spec["column_role"])
        for value in _option_values(roster, name, spec):
            out = roster_metrics.apply_filters(roster, {name: value})
            assert len(out) > 0, f"{name}={value!r} returned 0 rows"
            if column is not None:
                actual = set(out[column].astype(str).unique())
                assert actual == {value}, (
                    f"{name}={value!r} leaked non-matching rows: {actual}"
                )


def test_single_value_filters_partition_the_roster(roster):
    """Each row belongs to exactly one bucket, so summing every option's row
    count reproduces the total. Catches both over-matching and any option that
    silently matches nothing."""
    total = len(roster)
    for name, spec in _server_filters().items():
        if "derived_from_chart" in spec:
            continue  # derived bands are covered by the derived test below
        column = metric_config.column(spec["column_role"])
        # Only columns without blanks partition cleanly; the real roster has
        # no blanks in these, assert that assumption explicitly.
        assert roster[column].notna().all(), f"{column} has blanks; revisit test"
        counts = {
            v: len(roster_metrics.apply_filters(roster, {name: v}))
            for v in _option_values(roster, name, spec)
        }
        assert sum(counts.values()) == total, (
            f"{name} did not partition roster: sum={sum(counts.values())} "
            f"!= {total}"
        )


def test_derived_filters_partition_via_chart_labels(roster):
    """Experience / Seniority Category reuse a chart's bucketing, so filtering
    by a band must match exactly the rows that chart assigns to that band."""
    total = len(roster)
    for name in _derived_filters():
        spec = metric_config.filters()[name]
        chart = metric_config.chart(spec["derived_from_chart"])
        labels = roster_metrics.chart_labels(roster, chart).astype(str)
        covered = 0
        for value in sorted(labels.unique()):
            out = roster_metrics.apply_filters(roster, {name: value})
            expected = int((labels == value).sum())
            assert len(out) == expected, (
                f"{name}={value!r}: {len(out)} rows, chart assigns {expected}"
            )
            covered += len(out)
        assert covered == total, f"{name} bands do not cover every row"


def test_grade_filter_is_declared_and_works(roster):
    """Regression: the Workforce Grade dropdown existed but wasn't a declared
    filter, so selecting a grade did nothing."""
    assert "grade" in metric_config.filters()
    column = metric_config.column("grade")
    a_grade = sorted(roster[column].dropna().astype(str).unique())[0]
    out = roster_metrics.apply_filters(roster, {"grade": a_grade})
    assert 0 < len(out) < len(roster)
    assert set(out[column].astype(str).unique()) == {a_grade}


def test_region_market_hierarchy(roster):
    """Market nests strictly under Region: every Market belongs to exactly
    one Region, and filtering Region+Market together equals filtering by the
    Market alone (the hierarchy makes the extra Region redundant, never
    contradictory). Regression for the cascading Region>Market filter."""
    assert "market" in metric_config.filters()
    region_col = metric_config.column("region")
    market_col = metric_config.column("market")

    # Each market maps to exactly one region.
    for market, grp in roster.groupby(market_col):
        regions = grp[region_col].astype(str).unique()
        assert len(regions) == 1, f"market {market!r} spans regions {list(regions)}"
        region = str(regions[0])
        by_market = roster_metrics.apply_filters(roster, {"market": str(market)})
        by_both = roster_metrics.apply_filters(
            roster, {"region": region, "market": str(market)}
        )
        assert len(by_market) == len(by_both) > 0


def test_multi_value_filter_is_or_within_field(roster):
    """A list value means "match any of these" — what the hierarchical
    Region/Market multi-select sends when several regions/markets are ticked.
    The union of two single-value results equals the multi-value result."""
    region_col = metric_config.column("region")
    regions = sorted(roster[region_col].astype(str).unique())[:2]
    a = roster_metrics.apply_filters(roster, {"region": regions[0]})
    b = roster_metrics.apply_filters(roster, {"region": regions[1]})
    both = roster_metrics.apply_filters(roster, {"region": regions})
    assert len(both) == len(a) + len(b)
    assert set(both[region_col].astype(str).unique()) == set(regions)


def test_api_reads_repeated_query_params_as_list(api, roster):
    """`?region=EMEA&region=AMER` (repeated) filters as OR-within-field over
    HTTP, proving _filter_params reads multi-value params via getlist."""
    headers = {"Authorization": f"Bearer {_token(api)}"}
    region_col = metric_config.column("region")
    regions = sorted(roster[region_col].astype(str).unique())[:2]
    single = [
        api.get(
            "/api/v1/roster/employees",
            params={"region": r, "limit": 500},
            headers=headers,
        ).json()["total"]
        for r in regions
    ]
    multi = api.get(
        "/api/v1/roster/employees",
        params=[("region", regions[0]), ("region", regions[1]), ("limit", 500)],
        headers=headers,
    ).json()["total"]
    assert multi == sum(single) > 0


def test_combined_filters_intersect(roster):
    """Two filters together return the intersection, never more than either
    alone."""
    active_status = metric_config.status_value("active")
    region = sorted(roster[metric_config.column("region")].astype(str).unique())[0]
    only_status = roster_metrics.apply_filters(roster, {"status": active_status})
    only_region = roster_metrics.apply_filters(roster, {"region": region})
    both = roster_metrics.apply_filters(
        roster, {"status": active_status, "region": region}
    )
    assert len(both) <= min(len(only_status), len(only_region))
    assert len(both) == len(
        only_status[only_status[metric_config.column("region")].astype(str) == region]
    )


def test_unknown_and_blank_filters_are_ignored(roster):
    """Unknown keys and blank values must be no-ops, never a crash or an
    empty result."""
    n = len(roster)
    assert len(roster_metrics.apply_filters(roster, {})) == n
    assert len(roster_metrics.apply_filters(roster, {"status": ""})) == n
    assert len(roster_metrics.apply_filters(roster, {"not_a_filter": "x"})) == n


# --------------------------------------------------------------------------- #
# 2. API guard — endpoints accept exactly the declared filters
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def api():
    with TestClient(app) as c:
        yield c


def _token(api) -> str:
    resp = api.post(
        "/api/auth/login", json={"email": SEED_EMAIL, "password": SEED_PASSWORD}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def test_api_applies_each_declared_filter(api, roster):
    """Hitting /roster/employees with each declared filter returns a subset,
    proving the config-driven _filter_params reads every declared filter."""
    headers = {"Authorization": f"Bearer {_token(api)}"}
    full = api.get("/api/v1/roster/employees?limit=500", headers=headers)
    assert full.status_code == 200, full.text
    total = full.json()["total"]

    for name, spec in _server_filters().items():
        value = _option_values(roster, name, spec)[0]
        resp = api.get(
            "/api/v1/roster/employees",
            params={name: value, "limit": 500},
            headers=headers,
        )
        assert resp.status_code == 200, f"{name}={value}: {resp.text}"
        got = resp.json()["total"]
        assert 0 < got <= total, f"{name}={value}: {got} not a subset of {total}"


def test_api_ignores_undeclared_query_param(api):
    """A query param that isn't a declared filter must not filter anything."""
    headers = {"Authorization": f"Bearer {_token(api)}"}
    base = api.get("/api/v1/roster/summary", headers=headers).json()
    spoofed = api.get(
        "/api/v1/roster/summary", params={"bogus": "xyz"}, headers=headers
    ).json()
    assert base == spoofed
