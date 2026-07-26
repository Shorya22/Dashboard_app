"""
Tests for backend/app/services/utilization_metrics.py.

Includes a small hand-built fixture test plus 5 permanent regression cases
against the real files, per data-model SKILL.md's "Task for data-agent
once both sheets are available" step 4: known employee/week/value
combinations that must never silently break.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

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
def sample_bookings_overview() -> pd.DataFrame:
    """
    Booking-shaped fixture for the Overview page's new booking-derived
    (Formula A, D1a) computation. Two employees x 2 weeks:
      Gina — week 1: 8 client / 2 internal (0.8); week 2: 8 client / 2 internal (0.8);
             period aggregate: 16/20 = 0.80.
      Hank — week 1: 6 client / 4 internal (0.6); week 2: 6 client / 4 internal (0.6);
             period aggregate: 12/20 = 0.60.
    Average Period Utilization = mean(0.80, 0.60) = 0.70.
    """
    return pd.DataFrame(
        [
            {"Employee": "Gina", "Monday of Week": pd.Timestamp("2026-05-04"), "Booked Hours Type": "Client Hours", "Employee Booked Hours": 8.0},
            {"Employee": "Gina", "Monday of Week": pd.Timestamp("2026-05-04"), "Booked Hours Type": "Internal Hours", "Employee Booked Hours": 2.0},
            {"Employee": "Gina", "Monday of Week": pd.Timestamp("2026-05-11"), "Booked Hours Type": "Client Hours", "Employee Booked Hours": 8.0},
            {"Employee": "Gina", "Monday of Week": pd.Timestamp("2026-05-11"), "Booked Hours Type": "Internal Hours", "Employee Booked Hours": 2.0},
            {"Employee": "Hank", "Monday of Week": pd.Timestamp("2026-05-04"), "Booked Hours Type": "Client Hours", "Employee Booked Hours": 6.0},
            {"Employee": "Hank", "Monday of Week": pd.Timestamp("2026-05-04"), "Booked Hours Type": "Internal Hours", "Employee Booked Hours": 4.0},
            {"Employee": "Hank", "Monday of Week": pd.Timestamp("2026-05-11"), "Booked Hours Type": "Client Hours", "Employee Booked Hours": 6.0},
            {"Employee": "Hank", "Monday of Week": pd.Timestamp("2026-05-11"), "Booked Hours Type": "Internal Hours", "Employee Booked Hours": 4.0},
        ]
    )


def test_get_utilization_overview(sample_bookings_overview):
    """
    Overview switched from ground-truth-sourced to booking-derived
    Formula A (D1a) on 2026-07-26 — see METRICS.md Page 8. Response
    shape unchanged; values now trace back to per-employee aggregate
    ratios of Client Hours over total logged hours.
    """
    overview = get_utilization_overview(sample_bookings_overview)
    # Per-employee period ratios: Gina 16/20=0.80, Hank 12/20=0.60; mean = 0.70.
    assert overview["average_period_utilization_pct"] == pytest.approx(0.70)
    assert overview["total_employees"] == 2
    # Latest week is 2026-05-11 — same per-employee ratios in that week
    # (Gina 8/10=0.80, Hank 6/10=0.60); mean = 0.70.
    assert overview["latest_week_utilization_pct"] == pytest.approx(0.70)
    trend = {row["week_start"]: row["avg_weekly_utilization_pct"] for row in overview["weekly_trend"]}
    # Weekly trend is aggregate-then-ratio at the WEEK level: sum(client
    # in week) / sum(total in week) across all employees. 2026-05-04:
    # 14/20 = 0.70; 2026-05-11: 14/20 = 0.70.
    assert trend["2026-05-04"] == pytest.approx(0.70)
    assert trend["2026-05-11"] == pytest.approx(0.70)
    # Bands: Gina 0.80 -> moderate, Hank 0.60 -> low.
    assert overview["utilization_split"] == {"high": 0, "moderate": 1, "low": 1}
    # Ranking desc by period ratio: Gina (0.80) then Hank (0.60).
    assert [row["employee"] for row in overview["employee_ranking"]] == ["Gina", "Hank"]


# --------------------------------------------------------------------------
# Regression tests against the real files
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_bookings() -> pd.DataFrame:
    if not (FIXTURES_DIR / "booking_snapshot.xlsx").exists():
        pytest.skip(f"real booking file not present at {DEFAULT_BOOKING_PATH}")
    return load_booking_data(FIXTURES_DIR / "booking_snapshot.xlsx")


@pytest.fixture(scope="module")
def real_ground_truth_long() -> pd.DataFrame:
    if not (FIXTURES_DIR / "ground_truth_snapshot.xlsx").exists():
        pytest.skip(f"real ground-truth file not present at {DEFAULT_GROUND_TRUTH_PATH}")
    return load_ground_truth_long(FIXTURES_DIR / "ground_truth_snapshot.xlsx")


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


def test_get_utilization_overview_real_file_shape(real_bookings):
    """
    Shape regression against the real booking file — Overview is now
    booking-derived (Formula A, D1a) as of 2026-07-26 so the exact
    values move with each data refresh (rather than pinning to the
    ground-truth's 41 employees / 0.7143 average). This asserts
    structural invariants that must hold on any real booking snapshot:

    - Overview reports the same number of distinct booking employees as
      `booking_metrics.get_total_employees`.
    - `average_period_utilization_pct` is a valid ratio in [0, 1].
    - The Utilization Split covers exactly the total employees
      (`high + moderate + low == total_employees`) — matches the
      `charts_account_for_everyone` design contract on the roster side.
    - Employee ranking is sorted descending.
    - The 10/152 residual mismatch versus the ground truth (see module
      docstring) is no longer surfaced by Overview and must be observed
      via `reconcile_weekly_utilization` (exercised by
      `test_reconciliation_confirms_formula_a` above).
    """
    from app.services import booking_metrics

    overview = get_utilization_overview(real_bookings)
    total = booking_metrics.get_total_employees(real_bookings)
    assert overview["total_employees"] == total
    assert 0.0 <= overview["average_period_utilization_pct"] <= 1.0
    assert 0.0 <= overview["latest_week_utilization_pct"] <= 1.0
    split = overview["utilization_split"]
    assert split["high"] + split["moderate"] + split["low"] == total
    ranking = [row["period_utilization_pct"] for row in overview["employee_ranking"]]
    assert ranking == sorted(ranking, reverse=True)
