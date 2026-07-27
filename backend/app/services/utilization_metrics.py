"""
Aggregation functions for weekly utilization, computed entirely from the
booking sheet (`Sheet1`).

Design notes (per api-conventions SKILL.md "Excel/DB swap boundary"):
- Every public function takes either a DataFrame or a `path` defaulting to
  the real Excel file, and returns a plain dict/scalar/DataFrame.
- Source column names are kept exactly as they appear in the Excel file.

Formula A (Client Hours / that employee's actual logged total that week)
was originally confirmed by reconciling against a ground-truth Power BI
export (`PowerBI_Ready_Utilization_May_2026.xlsx`, 2026-07-15: 142/152
matched employee/weeks, 93.4%, reproduced the export's `Weekly
Utilization %` exactly). As of 2026-07-27 that ground-truth file, its
loaders, and the reconciliation path have been removed entirely — the
roster and booking sheets are the only two data sources the app reads.
Formula A itself remains the confirmed formula and is unchanged.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from app.services.cache_utils import cache_on_df

logger = logging.getLogger(__name__)

CLIENT_HOURS_LABEL = "Client Hours"
INTERNAL_HOURS_LABEL = "Internal Hours"


def compute_weekly_utilization_formula_a(booking_df: pd.DataFrame) -> pd.DataFrame:
    """
    `Weekly Utilization %` (Formula A):

        Weekly Utilization % = Client Hours / (Client Hours + Internal Hours)

    computed per (`Employee`, `Monday of Week`) from the raw booking sheet
    -- i.e. the employee's ACTUAL logged total that week is the
    denominator, NOT a fixed standard-capacity figure.

    Reads: `Employee`, `Monday of Week`, `Booked Hours Type`,
    `Employee Booked Hours`.
    Edge cases:
      - Rows with `Booked Hours Type` outside {Client Hours, Internal
        Hours} are excluded from both numerator and denominator (none
        observed in the real file, but not assumed away).
      - An employee/week with zero total logged hours yields NaN
        (undefined utilization), not 0 -- avoids implying "0% utilized"
        for a week with no data at all, which is a different fact from
        "worked 0 client hours out of some logged total."
      - The fully-blank row noted in `booking_metrics.load_booking_data`
        is naturally excluded (NaN `Employee`/`Monday of Week` groups are
        dropped by `groupby(..., dropna=True)`, the pandas default).
    """
    df = booking_df.copy()
    df["Monday of Week"] = pd.to_datetime(df["Monday of Week"])
    pivot = (
        df.groupby(["Employee", "Monday of Week", "Booked Hours Type"])[
            "Employee Booked Hours"
        ]
        .sum()
        .unstack(fill_value=0.0)
        .reset_index()
    )
    if CLIENT_HOURS_LABEL not in pivot.columns:
        pivot[CLIENT_HOURS_LABEL] = 0.0
    if INTERNAL_HOURS_LABEL not in pivot.columns:
        pivot[INTERNAL_HOURS_LABEL] = 0.0
    pivot["Total Hours"] = pivot[CLIENT_HOURS_LABEL] + pivot[INTERNAL_HOURS_LABEL]
    pivot["Weekly Utilization %"] = pivot[CLIENT_HOURS_LABEL] / pivot["Total Hours"].replace(
        0, pd.NA
    )
    return pivot[
        ["Employee", "Monday of Week", CLIENT_HOURS_LABEL, INTERNAL_HOURS_LABEL, "Total Hours", "Weekly Utilization %"]
    ]


@cache_on_df
def get_utilization_overview(booking_df: pd.DataFrame) -> dict:
    """
    KPIs / trend / split / ranking for the Utilization Overview page,
    computed ENTIRELY from the booking sheet using Formula A (see this
    module's top-of-file docstring).

    Per-employee "period" ratio (D1a — aggregate-then-ratio):

        period_util_pct[e] = sum(client_hours over period, for e)
                           / sum(all logged hours over period, for e)

    then the headline "Average Period Utilization %" is the mean of that
    per-employee vector — this gives every logged hour equal weight rather
    than weighting a partial week the same as a full one.

    The two headline KPIs and the two per-group charts all route through
    the config-driven dispatcher on `configs/booking_metrics.yaml`:

      cards.average_period_utilization_pct  (avg_of_chart on
        employee_period_utilization)
      cards.latest_week_utilization_pct     (avg_of_chart on the same
        chart, restricted to the latest Monday of Week)
      charts.employee_period_utilization    (ratio_by employee)
      charts.weekly_utilization_trend       (ratio_by week_start)
      charts.utilization_split              (ratio_bands over the
        employee ratios, thresholds still PROVISIONAL — see Page 8)

    Returns the same dict shape as before (frontend contract):
      {
        "average_period_utilization_pct": float,  # 0-1
        "total_employees": int,                   # distinct booking employees
        "latest_week_utilization_pct": float,     # 0-1, latest Monday of Week
        "weekly_trend": [{"week_start": str, "avg_weekly_utilization_pct": float}, ...],
        "utilization_split": {"high": int, "moderate": int, "low": int},
        "employee_ranking": [{"employee": str, "period_utilization_pct": float}, ...],  # desc
      }

    """
    from app.services import booking_metrics

    df = booking_df

    # Route KPIs through the declared cards so the values in the KPI strip
    # cannot drift from the chart values they summarise (same design
    # contract as records_summary_reuses_declared_cards on the roster side).
    average_period_pct = float(
        booking_metrics.evaluate_booking_card(df, "average_period_utilization_pct")
    )
    latest_week_pct = float(
        booking_metrics.evaluate_booking_card(df, "latest_week_utilization_pct")
    )

    # Weekly trend — Formula A per Monday of Week, one point per week.
    weekly_ratios = booking_metrics.evaluate_booking_chart(df, "weekly_utilization_trend")
    # `evaluate_booking_chart` returns {week_iso_string: ratio}; the input
    # keys come out of pandas as `str(Timestamp)` (e.g. "2026-05-04 00:00:00")
    # — normalise to date-only YYYY-MM-DD to match the frontend's
    # `WeeklyUtilizationTrendPoint.week_start` contract.
    def _to_iso_date(key: str) -> str:
        try:
            return pd.Timestamp(key).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            return str(key)

    weekly_trend = sorted(
        (
            {"week_start": _to_iso_date(k), "avg_weekly_utilization_pct": float(v)}
            for k, v in weekly_ratios.items()
        ),
        key=lambda item: item["week_start"],
    )

    # Utilization split — band counts over per-employee ratios.
    utilization_split_raw = booking_metrics.evaluate_booking_chart(df, "utilization_split")
    utilization_split = {
        "high": int(utilization_split_raw.get("high", 0)),
        "moderate": int(utilization_split_raw.get("moderate", 0)),
        "low": int(utilization_split_raw.get("low", 0)),
    }

    # Employee ranking — per-employee Formula A, sorted desc.
    employee_ratios = booking_metrics.evaluate_booking_chart(df, "employee_period_utilization")
    employee_ranking = sorted(
        (
            {"employee": str(emp), "period_utilization_pct": float(pct)}
            for emp, pct in employee_ratios.items()
        ),
        key=lambda item: item["period_utilization_pct"],
        reverse=True,
    )

    return {
        "average_period_utilization_pct": average_period_pct,
        "total_employees": int(
            booking_metrics.evaluate_booking_card(df, "total_employees_booking")
        ),
        "latest_week_utilization_pct": latest_week_pct,
        "weekly_trend": weekly_trend,
        "utilization_split": utilization_split,
        "employee_ranking": employee_ranking,
    }


def get_weekly_utilization_pct(
    booking_df: pd.DataFrame, employee: str, monday_of_week: str | pd.Timestamp
) -> float | None:
    """
    `Weekly Utilization %` for a single (employee, week) -- CONFIRMED
    Formula A per this module's reconciliation (see module docstring).
    Thin convenience wrapper around `compute_weekly_utilization_formula_a`
    for callers that want one employee/week rather than the full table.

    Reads: `Employee`, `Monday of Week`, `Booked Hours Type`,
    `Employee Booked Hours`.
    Edge cases: returns None if the employee/week combination has no
    booking rows at all, or if it exists but with zero total logged hours
    (undefined utilization -- see `compute_weekly_utilization_formula_a`).
    """
    all_weeks = compute_weekly_utilization_formula_a(booking_df)
    week_ts = pd.to_datetime(monday_of_week)
    row = all_weeks[
        (all_weeks["Employee"] == employee) & (all_weeks["Monday of Week"] == week_ts)
    ]
    if row.empty:
        return None
    value = row.iloc[0]["Weekly Utilization %"]
    if pd.isna(value):
        return None
    return float(value)
