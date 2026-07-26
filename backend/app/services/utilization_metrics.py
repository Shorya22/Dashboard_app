"""
Aggregation + reconciliation functions for weekly utilization, bridging the
booking sheet (`Sheet1`) and the ground-truth utilization export
(`UtilizationLongTable` in the real Power BI model), sourced from
`backend/data/PowerBI_Ready_Utilization_May_2026.xlsx`.

Design notes (per api-conventions SKILL.md "Excel/DB swap boundary"):
- Every public function takes either a DataFrame or a `path` defaulting to
  the real Excel file, and returns a plain dict/scalar/DataFrame.
- Source column names are kept exactly as they appear in the Excel file.

STATUS (2026-07-15): the booking sheet was replaced with a 1523-row / 7-week
export (2026-04-13 .. 2026-05-25) and the ground-truth file was found to
have real sheet names (`README`, `Employee_Weekly_Wide`,
`Utilization_Long`) rather than a single default sheet. `Utilization_Long`
covers 2026-05-04 .. 2026-05-25 (4 weeks), which DOES overlap the booking
sheet's last 4 weeks -- the "Confirmed blocker: no overlapping week"
section in data-model SKILL.md is now RESOLVED. Reconciliation was run
(see `reconcile_weekly_utilization` below): **Formula A (Client Hours /
that employee's actual logged total that week) is confirmed as the correct
formula** -- 142/152 matched employee/weeks (93.4%) reproduce the ground
truth's `Weekly Utilization %` exactly to 3 decimal places; Formula B
(fixed 45hr capacity denominator) only matches 122/152 (80.3%) and is
ruled out. The remaining 10/152 rows (Harsh Kharbanda, Lodagala Suresh,
Suraj Kayade -- all partial-week loggers) are within ~0.3-0.4 percentage
points of Formula A but not bit-exact; this residual is logged as an
UNRESOLVED data-quality flag (`utilization_formula_a_residual_mismatch`),
not silently smoothed over. It is most likely explained by either a small
number of additional/missing booking rows for those three employees in
those specific weeks, or day-level hour rounding upstream of this export --
neither has been confirmed against a further source, so do not treat this
as "fully bit-exact for every row," only "formula confirmed, ~93% exact."

Per data-model SKILL.md's "Flagged discrepancies" section: the underlying
`Weekly Utilization %` CALCULATED COLUMN's own DAX formula body (as opposed
to the aggregation-layer measures built on top of it) has still not been
shared -- this module's empirical match against the ground-truth sheet
does NOT substitute for that confirmation, it only confirms that Formula A
reproduces the same *output* on this dataset. Keep both facts distinct.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from app.services.cache_utils import cache_on_df

logger = logging.getLogger(__name__)

DEFAULT_GROUND_TRUTH_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "PowerBI_Ready_Utilization_May_2026.xlsx"
)

GROUND_TRUTH_LONG_SHEET = "Utilization_Long"
GROUND_TRUTH_WIDE_SHEET = "Employee_Weekly_Wide"

STANDARD_WEEKLY_CAPACITY_HOURS = 45.0  # Formula B candidate -- CONFIRMED WRONG, kept only for the reconciliation function / tests

CLIENT_HOURS_LABEL = "Client Hours"
INTERNAL_HOURS_LABEL = "Internal Hours"

# Best-effort name-variant map, booking-sheet spelling -> ground-truth
# spelling, confirmed via first+last token matching to 4 of the 5 cases
# already documented in `.claude/skills/data-model/known-name-variants.md`
# (that file mapped the ground-truth spelling as canonical; this map goes
# the other direction, booking -> ground-truth, since ground-truth is this
# module's reference). UNCONFIRMED by a human -- treat as provisional, per
# that file's own instructions.
#
# RESOLVED AT SOURCE (2026-07-17): "Kaginthala Reddy" -> "Kagithala Reddy",
# "Saumyarajan Kanungo" -> "Saumyaranjan Kanungo", and "Suraj Kayade" ->
# "Suraj Kavade" were corrected directly in the ground-truth Excel file
# at the business owner's direction (matching the booking sheet's
# spelling, which was already correct) -- same resolution pattern as the
# "Ankit Singh" -> "Amit Singh" fix below. All 3 entries removed from
# this map: the booking sheet's spelling now matches the ground truth
# directly, so translating it through the old mapping would look up a
# name that no longer exists in the ground truth file and silently drop
# those employee/weeks from every reconciliation.
#
# RESOLVED AT SOURCE (2026-07-21): "Pramod Kabugande" -> "Pramod Kabugade"
# corrected directly in the ground-truth Excel (5 cells across
# Utilization_Long + Employee_Weekly_Wide), confirmed by the business
# owner -- the roster and booking sheets already used the correct
# "Kabugade". Its map entry is removed for the same reason as the
# 2026-07-17 fixes: with the ground truth now spelling it "Kabugade",
# mapping booking's (correct) "Kabugade" to the old typo would look up a
# name that no longer exists and silently drop those employee/weeks from
# reconciliation. A backup of the pre-fix workbook is in
# `backend/data/backups/`.
BOOKING_TO_GROUND_TRUTH_NAME_MAP: dict[str, str] = {
    # "Amit Singh" (booking) vs "Ankit Singh" (ground truth) is NEW as of
    # this pass and NOT in known-name-variants.md -- deliberately left
    # UNMAPPED here. Could be a genuine typo-variant of the same person,
    # or two different people ("Amit" vs "Ankit" are both common given
    # names). Needs a human answer before being added to this map -- do
    # not guess silently.
}


def load_ground_truth_long(
    path: str | Path = DEFAULT_GROUND_TRUTH_PATH,
) -> pd.DataFrame | None:
    """
    Read the `Utilization_Long` sheet of the ground-truth utilization
    workbook (one row per employee per week). The workbook's FIRST sheet
    (`README`) is a documentation preamble with a different shape entirely
    (a 2-column sheet/purpose index) -- confirmed via
    `pd.ExcelFile(path).sheet_names` to be `["README",
    "Employee_Weekly_Wide", "Utilization_Long"]`. `Utilization_Long` itself
    has its real header in row 0 (no extra preamble rows on this sheet, only
    on `README`), so plain `header=0` is correct here.

    Returns the raw DataFrame (164 rows / 41 distinct employees / 4 weeks
    -- 2026-05-04 through 2026-05-25 -- in the file confirmed 2026-07-15),
    or `None` if the file is absent.

    As of 2026-07-26 the ground-truth file is OPTIONAL: Overview no longer
    reads it at runtime (see `get_utilization_overview` — booking-derived
    Formula A). This loader survives only for the QA reconcile path
    (`/api/v1/qa/reconcile`) and is called lazily on demand there. Callers
    must handle `None` (404 with a helpful body on the QA endpoint;
    disable / no-op elsewhere).
    """
    path_obj = Path(path)
    if not path_obj.exists():
        logger.info(
            "load_ground_truth_long: file %s not found — returning None "
            "(runtime path no longer requires this file; only QA reconcile does)",
            path_obj,
        )
        return None
    df = pd.read_excel(path_obj, sheet_name=GROUND_TRUTH_LONG_SHEET, header=0)
    df["Week Start"] = pd.to_datetime(df["Week Start"])
    logger.info(
        "load_ground_truth_long: read %d rows (%d distinct employees) from %s [%s]",
        len(df),
        df["Employee"].nunique(),
        path,
        GROUND_TRUTH_LONG_SHEET,
    )
    return df


def load_ground_truth_wide(path: str | Path = DEFAULT_GROUND_TRUTH_PATH) -> pd.DataFrame:
    """
    Read the `Employee_Weekly_Wide` sheet (one row per employee, four
    weekly utilization columns + `Period Total Utilization %`). Provided
    for completeness / future use -- no aggregation function in this
    module currently reads it, `Utilization_Long` is the reconciliation
    source since it's already in the row-per-employee-per-week shape this
    module's utilization function needs to match against.
    """
    df = pd.read_excel(path, sheet_name=GROUND_TRUTH_WIDE_SHEET, header=0)
    logger.info(
        "load_ground_truth_wide: read %d rows from %s [%s]",
        len(df),
        path,
        GROUND_TRUTH_WIDE_SHEET,
    )
    return df


def compute_weekly_utilization_formula_a(booking_df: pd.DataFrame) -> pd.DataFrame:
    """
    `Weekly Utilization %` (Formula A -- CONFIRMED via reconciliation
    against the real `Utilization_Long` ground-truth sheet, 2026-07-15):

        Weekly Utilization % = Client Hours / (Client Hours + Internal Hours)

    computed per (`Employee`, `Monday of Week`) from the raw booking sheet
    -- i.e. the employee's ACTUAL logged total that week is the
    denominator, NOT a fixed standard-capacity figure (Formula B, ruled
    out: see module docstring).

    NOTE: this reproduces the ground truth's *output* empirically; the
    ground-truth sheet's own underlying calculated-column DAX formula is
    still unconfirmed (per data-model SKILL.md's "Flagged discrepancies").
    Treat this function as "empirically validated, formula body
    unconfirmed" -- not the same as a DAX-verified measure.

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


def reconcile_weekly_utilization(
    booking_df: pd.DataFrame,
    ground_truth_long_df: pd.DataFrame,
    tolerance: float = 0.0006,
    apply_name_map: bool = True,
) -> dict:
    """
    Independently compute utilization from raw booking hours (both Formula
    A and Formula B) and compare against the ground truth's
    `Weekly Utilization %`, per data-model SKILL.md's "Task for data-agent
    once both sheets are available".

    Returns a dict:
      {
        "matched_employee_weeks": int,          # rows present in both, after name mapping
        "formula_a_exact_matches": int,          # within `tolerance` of ground truth
        "formula_b_exact_matches": int,
        "formula_a_match_rate": float,           # 0-1
        "formula_b_match_rate": float,
        "mismatches": list[dict],                # formula_a rows outside tolerance
        "unmatched_ground_truth_employee_weeks": list[dict],  # no booking-side match
      }

    `apply_name_map=True` (default) applies
    `BOOKING_TO_GROUND_TRUTH_NAME_MAP` before joining, matching this
    module's confirmed reconciliation result (142/152 = 93.4% Formula A
    exact matches). Pass `False` to see the raw exact-name-only join.
    """
    computed = compute_weekly_utilization_formula_a(booking_df)
    computed["Formula B"] = computed[CLIENT_HOURS_LABEL] / STANDARD_WEEKLY_CAPACITY_HOURS

    if apply_name_map:
        computed["Employee"] = computed["Employee"].replace(BOOKING_TO_GROUND_TRUTH_NAME_MAP)

    gt = ground_truth_long_df.copy()
    gt["Week Start"] = pd.to_datetime(gt["Week Start"])

    merged = gt.merge(
        computed,
        left_on=["Employee", "Week Start"],
        right_on=["Employee", "Monday of Week"],
        how="left",
        indicator=True,
    )

    matched = merged[merged["_merge"] == "both"].copy()
    unmatched = merged[merged["_merge"] == "left_only"]

    matched["diff_a"] = (matched["Weekly Utilization %_x"] - matched["Weekly Utilization %_y"]).abs()
    matched["diff_b"] = (matched["Weekly Utilization %_x"] - matched["Formula B"]).abs()

    a_ok = matched["diff_a"] <= tolerance
    b_ok = matched["diff_b"] <= tolerance

    mismatches = [
        {
            "employee": row["Employee"],
            "week_start": row["Week Start"].strftime("%Y-%m-%d"),
            "ground_truth_pct": row["Weekly Utilization %_x"],
            "formula_a_pct": row["Weekly Utilization %_y"],
            "diff": row["diff_a"],
        }
        for _, row in matched[~a_ok].iterrows()
    ]

    unmatched_list = [
        {"employee": row["Employee"], "week_start": row["Week Start"].strftime("%Y-%m-%d")}
        for _, row in unmatched.iterrows()
    ]

    n = len(matched)
    result = {
        "matched_employee_weeks": n,
        "formula_a_exact_matches": int(a_ok.sum()),
        "formula_b_exact_matches": int(b_ok.sum()),
        "formula_a_match_rate": (a_ok.sum() / n) if n else 0.0,
        "formula_b_match_rate": (b_ok.sum() / n) if n else 0.0,
        "mismatches": mismatches,
        "unmatched_ground_truth_employee_weeks": unmatched_list,
    }
    logger.info(
        "reconcile_weekly_utilization: %d matched, Formula A %d/%d (%.1f%%), "
        "Formula B %d/%d (%.1f%%)",
        n,
        result["formula_a_exact_matches"],
        n,
        result["formula_a_match_rate"] * 100,
        result["formula_b_exact_matches"],
        n,
        result["formula_b_match_rate"] * 100,
    )
    return result


@cache_on_df
def get_utilization_overview(booking_df: pd.DataFrame) -> dict:
    """
    KPIs / trend / split / ranking for the Utilization Overview page,
    computed ENTIRELY from the booking sheet using Formula A (see this
    module's top-of-file docstring for the empirical confirmation).

    As of 2026-07-26 the ground-truth `Utilization_Long` sheet is NO
    LONGER consulted at runtime — it survives only as a QA reconciliation
    input via `reconcile_weekly_utilization` and the `/api/v1/qa/reconcile`
    admin endpoint. See METRICS.md Page 8 for the rationale and for the
    numbers-will-change note (booking has 46 employees vs the ground
    truth's 41, and covers 7 weeks vs 4). The response SHAPE is unchanged
    so the frontend needs no changes; the VALUES move by construction.

    Per-employee "period" ratio (D1a — aggregate-then-ratio):

        period_util_pct[e] = sum(client_hours over period, for e)
                           / sum(all logged hours over period, for e)

    then the headline "Average Period Utilization %" is the mean of that
    per-employee vector. Rationale: the ground-truth column is literally
    called "Period Total Utilization %" — "period total" reads as
    aggregate-then-ratio, and it also gives every logged hour equal weight
    rather than weighting a partial week the same as a full one.

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

    The 10/152 residual mismatches between Formula A and the ground
    truth's shipped `Weekly Utilization %` (see this module's top
    docstring) no longer surface on the runtime Overview — they can only
    be observed by hitting `/api/v1/qa/reconcile` with the ground-truth
    file present. Not a data-quality regression: the runtime always used
    Formula A's shape, the ground truth only agreed on 142/152 rows.
    """
    # Deliberately not importing at module top: `booking_metrics` imports
    # `utilization_metrics.load_ground_truth_long` via `data_loader`, so
    # a top-level import here would be a cycle. Local import keeps the
    # module-load DAG one-way.
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
