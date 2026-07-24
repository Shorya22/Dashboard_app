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
    """Every filter that runs through `apply_filters` as a plain column
    match. Excludes `time_filter: true` filters (Month/Year), whose values
    are "Mon YYYY" labels that don't map to distinct column values — those
    get their own dedicated test below (`test_month_year_time_filter_*`)."""
    return {
        name: spec
        for name, spec in metric_config.filters().items()
        if not spec.get("time_filter")
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


# Cache the login token per test module: the /auth/login route is rate
# limited to 5/min and this file now has enough tests to blow past that
# if each one logs in fresh (was flaky under -q parallel runs). One
# login per module reproduces the shared-token pattern used elsewhere.
_TOKEN_CACHE: dict[int, str] = {}


def _token(api) -> str:
    key = id(api)
    if key not in _TOKEN_CACHE:
        resp = api.post(
            "/api/auth/login", json={"email": SEED_EMAIL, "password": SEED_PASSWORD}
        )
        assert resp.status_code == 200, resp.text
        _TOKEN_CACHE[key] = resp.json()["access_token"]
    return _TOKEN_CACHE[key]


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


def _first_available_month(api, headers) -> str:
    """First "Mon YYYY" label the unfiltered trends endpoint emits — the
    same list the frontend Month/Year picker builds from, so a value
    picked here is guaranteed to match at least one row."""
    resp = api.get("/api/v1/roster/trends", headers=headers)
    assert resp.status_code == 200, resp.text
    months = [m["month"] for m in resp.json()["month_wise_closing_headcount"]]
    assert months, "roster trends returned no months — cannot exercise month_year"
    return months[0]


def test_month_year_time_filter_narrows_roster_rows(roster):
    """The `time_filter: true` branch of `apply_filters` keeps only rows
    active during at least one selected month (DOJ ≤ end-of-M AND (LWD
    null OR LWD ≥ start-of-M)) — never the full roster, never zero
    rows for a valid label, never a plain column-value match."""
    doj_col = metric_config.column("joining_date")
    # Pick a month clearly inside the roster's DOJ range — first non-null
    # DOJ month. `%b %Y` matches the trend endpoint's own label format.
    dojs = pd.to_datetime(roster[doj_col], format="%d-%b-%y", errors="coerce")
    a_month = dojs.dropna().sort_values().iloc[0].strftime("%b %Y")
    narrowed = roster_metrics.apply_filters(roster, {"month_year": a_month})
    assert 0 < len(narrowed) <= len(roster)
    # Everyone in the narrowed frame either has DOJ ≤ end-of-M, OR has
    # a blank DOJ (DAX BLANK() parity — see `_apply_month_year_filter`
    # and `get_closing_headcount`'s already-established rule that a
    # blank DOJ is still part of the workforce).
    end_of_m = pd.to_datetime(a_month, format="%b %Y") + pd.offsets.MonthEnd(0)
    narrowed_dojs = pd.to_datetime(
        narrowed[doj_col], format="%d-%b-%y", errors="coerce"
    )
    assert (narrowed_dojs.isna() | (narrowed_dojs <= end_of_m)).all()


def test_month_year_time_filter_empty_selection_returns_empty(roster):
    """A malformed / unparseable month label narrows to zero rows rather
    than silently returning the whole roster — matches every other
    filter's "no valid values" contract."""
    out = roster_metrics.apply_filters(roster, {"month_year": ["not-a-month"]})
    assert len(out) == 0


def test_month_year_multi_value_is_or_within_field(roster):
    """Two months ORed within `month_year` return the union of each
    single-month result — same shape as the region multi-value test."""
    doj_col = metric_config.column("joining_date")
    dojs = pd.to_datetime(roster[doj_col], format="%d-%b-%y", errors="coerce").dropna()
    labels = sorted({d.strftime("%b %Y") for d in dojs})[:2]
    if len(labels) < 2:
        pytest.skip("roster has only one DOJ month — cannot exercise OR")
    a = roster_metrics.apply_filters(roster, {"month_year": labels[0]})
    b = roster_metrics.apply_filters(roster, {"month_year": labels[1]})
    both = roster_metrics.apply_filters(roster, {"month_year": labels})
    # OR: everyone in either single-picked set is in the union; and no
    # extra rows (the multi-value contract).
    expected = set(a.index) | set(b.index)
    assert set(both.index) == expected


def test_api_month_year_narrows_kpis_and_trends(api):
    """HR Analytics contract: picking a month narrows /roster/summary
    (KPIs) AND /roster/trends (monthly arrays) AND /roster/attrition-detail
    (monthly resignation) in one round trip. This is the user-visible
    guarantee that Month/Year is now a real server-side filter, not a
    client-only membership check that only touched some charts."""
    headers = {"Authorization": f"Bearer {_token(api)}"}
    month = _first_available_month(api, headers)

    unfiltered_summary = api.get("/api/v1/roster/summary", headers=headers).json()
    filtered_summary = api.get(
        "/api/v1/roster/summary", params={"month_year": month}, headers=headers
    ).json()
    # Total Employees is a distinct-employee-id count; narrowing to one
    # month can never return MORE people than the full roster.
    assert filtered_summary["total_employees"] <= unfiltered_summary["total_employees"]

    trends = api.get(
        "/api/v1/roster/trends", params={"month_year": month}, headers=headers
    ).json()
    months_in_trend = {row["month"] for row in trends["month_wise_closing_headcount"]}
    assert months_in_trend == {month}
    jvl_months = {row["month"] for row in trends["monthly_joiners_vs_leavers"]}
    assert jvl_months == {month}

    attrition = api.get(
        "/api/v1/roster/attrition-detail",
        params={"month_year": month},
        headers=headers,
    ).json()
    resig_months = {row["month"] for row in attrition["month_wise_resignation"]}
    # Resignation is a subset — months with zero exits are dropped from
    # the trend by the underlying series, so the ticked month may or may
    # not appear. What must NEVER appear is any OTHER month.
    assert resig_months.issubset({month})


def _lwd_months(roster) -> list[str]:
    """"Mon YYYY" labels the roster actually has an LWD in — used to
    exercise the exit-shaped KPI window. Empty when the fixture has no
    exits at all (skip the test in that case)."""
    lwd_col = metric_config.column("leaving_date")
    lwds = pd.to_datetime(roster[lwd_col], format="%d-%b-%y", errors="coerce").dropna()
    return sorted({d.strftime("%b %Y") for d in lwds})


def test_month_year_exits_kpi_counts_lwd_in_window_not_currently_inactive(api, roster):
    """The reported bug: picking a window that DOES NOT contain anyone's
    LWD must return Exits = 0, even though some Inactive employees
    (with LWD outside the window) are on the current roster. Previously
    `Exits` counted "current Status == Inactive" over the active-during
    frame and picked up exits that happened outside the picked window.
    """
    headers = {"Authorization": f"Bearer {_token(api)}"}
    lwd_months = _lwd_months(roster)
    if not lwd_months:
        pytest.skip("roster has no LWDs — cannot exercise exit-window bug")

    # A month clearly earlier than any real LWD: 24 years before the
    # earliest one. Anyone active then may still be Inactive today, but
    # nobody exited in that month — Exits must be 0.
    earliest_lwd = pd.to_datetime(lwd_months[0], format="%b %Y")
    empty_window = (earliest_lwd - pd.DateOffset(years=24)).strftime("%b %Y")

    resp = api.get(
        "/api/v1/roster/summary",
        params={"month_year": empty_window},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["exits"] == 0, (
        f"exits should be 0 when the picked window contains no LWD, "
        f"got {body['exits']} — the KPI is silently counting currently-"
        f"Inactive employees whose LWD is outside {empty_window}"
    )
    assert body["voluntary_leavers"] == 0
    assert body["involuntary_leavers"] == 0
    assert body["inactive_employees"] == 0
    assert body["attrition_pct"] == 0.0


def test_month_year_exits_kpi_matches_lwd_in_window_count(api, roster):
    """Positive case: for a window that DOES contain LWDs, the Exits KPI
    equals the count of roster rows with LWD in that window — the same
    rule the Month-Wise Resignation chart uses (`date_role: leaving_date`
    in the roster YAML)."""
    headers = {"Authorization": f"Bearer {_token(api)}"}
    lwd_months = _lwd_months(roster)
    if not lwd_months:
        pytest.skip("roster has no LWDs — cannot exercise the positive case")
    month = lwd_months[0]
    lwd_col = metric_config.column("leaving_date")
    lwds = pd.to_datetime(roster[lwd_col], format="%d-%b-%y", errors="coerce")
    month_start = pd.to_datetime(month, format="%b %Y")
    month_end = month_start + pd.offsets.MonthEnd(0)
    expected = int(((lwds >= month_start) & (lwds <= month_end)).sum())

    body = api.get(
        "/api/v1/roster/summary",
        params={"month_year": month},
        headers=headers,
    ).json()
    assert body["exits"] == expected, (
        f"Exits KPI should equal LWD-in-window count for {month}: "
        f"expected {expected}, got {body['exits']}"
    )


def test_month_year_voluntary_involuntary_donut_counts_only_in_window(api, roster):
    """Donut = exit reason split over LWD-in-window rows. An out-of-window
    exit must not contribute to either slice, otherwise a 2025 pick
    would show 2026-Apr exits under "Voluntary" — the reported bug."""
    headers = {"Authorization": f"Bearer {_token(api)}"}
    lwd_months = _lwd_months(roster)
    if not lwd_months:
        pytest.skip("roster has no LWDs")
    earliest_lwd = pd.to_datetime(lwd_months[0], format="%b %Y")
    empty_window = (earliest_lwd - pd.DateOffset(years=24)).strftime("%b %Y")

    body = api.get(
        "/api/v1/roster/attrition-detail",
        params={"month_year": empty_window},
        headers=headers,
    ).json()
    # The donut is the `voluntary_involuntary_split` dict. Every value
    # must be 0 for an empty window.
    assert all(v == 0 for v in body["voluntary_involuntary_split"].values()), (
        f"voluntary_involuntary_split should be all-zero for a window "
        f"with no LWDs, got {body['voluntary_involuntary_split']}"
    )
    # Exits table likewise: rows in this list are LWD-in-window rows only.
    assert body["exits_table"] == []


def test_month_year_attrition_pct_reflects_in_window_exits(api, roster):
    """Attrition % has to move with the LWD-in-window Exits count: a
    window with zero exits is 0.0%, and a window WITH exits is > 0.
    Guards the specific regression the coordinator flagged (KPI showed
    21.1% for 2025 while the Month-Wise Resignation chart on the same
    page said 0 exits happened in 2025)."""
    headers = {"Authorization": f"Bearer {_token(api)}"}
    lwd_months = _lwd_months(roster)
    if not lwd_months:
        pytest.skip("roster has no LWDs")

    # An empty window: attrition_pct must be exactly 0.
    earliest_lwd = pd.to_datetime(lwd_months[0], format="%b %Y")
    empty_window = (earliest_lwd - pd.DateOffset(years=24)).strftime("%b %Y")
    empty = api.get(
        "/api/v1/roster/summary",
        params={"month_year": empty_window},
        headers=headers,
    ).json()
    assert empty["attrition_pct"] == 0.0, empty["attrition_pct"]

    # A window that CONTAINS an LWD: attrition_pct must be > 0 and
    # bounded to [0, 100]. Positive lower bound is the anti-regression
    # (if the fix accidentally always returned 0, this catches it).
    with_lwd = api.get(
        "/api/v1/roster/summary",
        params={"month_year": lwd_months[0]},
        headers=headers,
    ).json()
    assert with_lwd["exits"] > 0
    assert 0.0 < with_lwd["attrition_pct"] <= 100.0, with_lwd["attrition_pct"]


def test_api_ignores_undeclared_query_param(api):
    """A query param that isn't a declared filter must not filter anything."""
    headers = {"Authorization": f"Bearer {_token(api)}"}
    base = api.get("/api/v1/roster/summary", headers=headers).json()
    spoofed = api.get(
        "/api/v1/roster/summary", params={"bogus": "xyz"}, headers=headers
    ).json()
    assert base == spoofed
