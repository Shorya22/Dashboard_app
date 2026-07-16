"""
Tests for backend/app/services/utilization_metrics.py.

Includes a small hand-built fixture test plus 5 permanent regression cases
against the real files, per data-model SKILL.md's "Task for data-agent
once both sheets are available" step 4: known employee/week/value
combinations that must never silently break.
"""

from __future__ import annotations

import pandas as pd
import pytest

from app.services.booking_metrics import DEFAULT_BOOKING_PATH, load_booking_data
from app.services.utilization_metrics import (
    DEFAULT_GROUND_TRUTH_PATH,
    compute_weekly_utilization_formula_a,
    get_utilization_overview,
    get_weekly_utilization_pct,
    load_ground_truth_long,
    reconcile_weekly_utilization,
)


@pytest.fixture
def sample_bookings() -> pd.DataFrame:
    """
    Hand-built: Dana logs a full 40hr week (30 client / 10 internal ->
    75% utilization), Eli logs a partial week (5 client / 5 internal ->
    50%), Fay logs an all-internal week (0 client / 8 internal -> 0%).
    """
    return pd.DataFrame(
        [
            {"Employee": "Dana", "Monday of Week": "2026-05-04", "Booked Hours Type": "Client Hours", "Employee Booked Hours": 30.0},
            {"Employee": "Dana", "Monday of Week": "2026-05-04", "Booked Hours Type": "Internal Hours", "Employee Booked Hours": 10.0},
            {"Employee": "Eli", "Monday of Week": "2026-05-04", "Booked Hours Type": "Client Hours", "Employee Booked Hours": 5.0},
            {"Employee": "Eli", "Monday of Week": "2026-05-04", "Booked Hours Type": "Internal Hours", "Employee Booked Hours": 5.0},
            {"Employee": "Fay", "Monday of Week": "2026-05-04", "Booked Hours Type": "Internal Hours", "Employee Booked Hours": 8.0},
        ]
    )


def test_compute_weekly_utilization_formula_a(sample_bookings):
    result = compute_weekly_utilization_formula_a(sample_bookings)
    result = result.set_index("Employee")
    assert result.loc["Dana", "Weekly Utilization %"] == pytest.approx(0.75)
    assert result.loc["Eli", "Weekly Utilization %"] == pytest.approx(0.50)
    assert result.loc["Fay", "Weekly Utilization %"] == pytest.approx(0.0)


def test_get_weekly_utilization_pct(sample_bookings):
    assert get_weekly_utilization_pct(sample_bookings, "Dana", "2026-05-04") == pytest.approx(0.75)
    assert get_weekly_utilization_pct(sample_bookings, "Nobody", "2026-05-04") is None


def test_get_weekly_utilization_pct_zero_total_is_none():
    df = pd.DataFrame(
        [{"Employee": "Zed", "Monday of Week": "2026-05-04", "Booked Hours Type": "Client Hours", "Employee Booked Hours": 0.0}]
    )
    assert get_weekly_utilization_pct(df, "Zed", "2026-05-04") is None


@pytest.fixture
def sample_ground_truth_long() -> pd.DataFrame:
    """
    Hand-built ground-truth long table: Gina (0.9, 0.7 -> Period 0.8),
    Hank (0.6, 0.6 -> Period 0.6), 2 weeks each.
    """
    return pd.DataFrame(
        [
            {"Employee": "Gina", "Week Start": "2026-05-04", "Weekly Utilization %": 0.9, "Period Total Utilization %": 0.8},
            {"Employee": "Gina", "Week Start": "2026-05-11", "Weekly Utilization %": 0.7, "Period Total Utilization %": 0.8},
            {"Employee": "Hank", "Week Start": "2026-05-04", "Weekly Utilization %": 0.6, "Period Total Utilization %": 0.6},
            {"Employee": "Hank", "Week Start": "2026-05-11", "Weekly Utilization %": 0.6, "Period Total Utilization %": 0.6},
        ]
    )


def test_get_utilization_overview(sample_ground_truth_long):
    overview = get_utilization_overview(sample_ground_truth_long)
    # average_period_pct = mean of per-employee Period Total: (0.8 + 0.6) / 2 = 0.7
    assert overview["average_period_utilization_pct"] == pytest.approx(0.7)
    assert overview["total_employees"] == 2
    # latest week is 2026-05-11: avg(Gina 0.7, Hank 0.6) = 0.65
    assert overview["latest_week_utilization_pct"] == pytest.approx(0.65)
    trend = {row["week_start"]: row["avg_weekly_utilization_pct"] for row in overview["weekly_trend"]}
    # 2026-05-04: avg(0.9, 0.6) = 0.75; 2026-05-11: avg(0.7, 0.6) = 0.65
    assert trend["2026-05-04"] == pytest.approx(0.75)
    assert trend["2026-05-11"] == pytest.approx(0.65)
    # bands: Gina 0.8 -> moderate (0.80 <= x < 0.90), Hank 0.6 -> low
    assert overview["utilization_split"] == {"high": 0, "moderate": 1, "low": 1}
    # ranking descending by Period Total Utilization %: Gina then Hank
    assert [row["employee"] for row in overview["employee_ranking"]] == ["Gina", "Hank"]


# --------------------------------------------------------------------------
# Regression tests against the real files
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_bookings() -> pd.DataFrame:
    if not DEFAULT_BOOKING_PATH.exists():
        pytest.skip(f"real booking file not present at {DEFAULT_BOOKING_PATH}")
    return load_booking_data()


@pytest.fixture(scope="module")
def real_ground_truth_long() -> pd.DataFrame:
    if not DEFAULT_GROUND_TRUTH_PATH.exists():
        pytest.skip(f"real ground-truth file not present at {DEFAULT_GROUND_TRUTH_PATH}")
    return load_ground_truth_long()


def test_reconciliation_confirms_formula_a(real_bookings, real_ground_truth_long):
    """
    Confirmed 2026-07-15, UPDATED 2026-07-16: Formula A (Client Hours /
    actual logged total) matches the ground truth's `Weekly Utilization %`
    (within the `tolerance=0.0006` default, i.e. ~half the sheet's
    3-decimal rounding step) for 147/156 (94.2%) of matched employee/weeks;
    Formula B (fixed 45hr capacity) only matches 124/156 (79.5%). This is
    the reconciliation result that resolves data-model SKILL.md's
    "Confirmed blocker: no overlapping week" and "Candidate formulas"
    sections.

    RESOLVED-AT-SOURCE UPDATE (2026-07-16): the ground-truth file's
    "Ankit Singh" typo was corrected to "Amit Singh" directly in the
    source Excel file (matching the roster's and booking sheet's
    spelling), so the name now matches directly instead of relying on
    the `known-name-variants` mapping for that one employee. This
    resolves 4 additional employee/weeks that previously fell through as
    unmatched due to the spelling mismatch (matched_employee_weeks:
    152 -> 156), and all 4 are exact Formula A matches (formula_a_exact_
    matches: 143 -> 147; formula_b_exact_matches: 122 -> 124), consistent
    with this employee's 100%-Client-Hours pattern already documented in
    the data-model skill.
    """
    result = reconcile_weekly_utilization(real_bookings, real_ground_truth_long)
    assert result["matched_employee_weeks"] == 156
    assert result["formula_a_exact_matches"] == 147
    assert result["formula_b_exact_matches"] == 124
    assert result["formula_a_match_rate"] > result["formula_b_match_rate"]


# 5 known-good employee/week/value combinations, hand-picked from the
# reconciliation as EXACT matches (diff == 0 to 3dp) -- permanent
# regression cases per data-model SKILL.md step 4.
@pytest.mark.parametrize(
    "employee,week_start,expected_pct",
    [
        ("Abhishek Modi", "2026-05-04", 1.000),
        ("Abhishek Modi", "2026-05-11", 0.800),
        ("Aishwarya Pawar", "2026-05-04", 0.800),
        ("Ajaykumar Kayande", "2026-05-04", 0.155556),
        ("Akash Barve", "2026-05-11", 0.888889),
    ],
)
def test_known_weekly_utilization_regression(real_bookings, employee, week_start, expected_pct):
    value = get_weekly_utilization_pct(real_bookings, employee, week_start)
    assert value == pytest.approx(expected_pct, abs=1e-4)


def test_get_utilization_overview_real_file(real_ground_truth_long):
    """
    Pins the reference values already confirmed in a prior validation pass
    (data-model SKILL.md / prior reconciliation work): ~71.43% average
    period utilization, ~69.09% latest week utilization. Independently
    recomputed here via `Utilization_Long.drop_duplicates('Employee')
    ['Period Total Utilization %'].mean()` == 0.7143170731707317, and
    `Utilization_Long[Week Start == max]['Weekly Utilization %'].mean()`
    == 0.690925 (latest week is 2026-05-25).
    """
    overview = get_utilization_overview(real_ground_truth_long)
    assert overview["average_period_utilization_pct"] == pytest.approx(0.714317, abs=1e-4)
    assert overview["latest_week_utilization_pct"] == pytest.approx(0.690925, abs=1e-4)
    assert overview["total_employees"] == 41
    assert overview["utilization_split"] == {"high": 15, "moderate": 8, "low": 18}
