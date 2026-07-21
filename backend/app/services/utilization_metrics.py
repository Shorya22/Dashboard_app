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


def load_ground_truth_long(path: str | Path = DEFAULT_GROUND_TRUTH_PATH) -> pd.DataFrame:
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
    -- 2026-05-04 through 2026-05-25 -- in the file confirmed 2026-07-15).
    """
    df = pd.read_excel(path, sheet_name=GROUND_TRUTH_LONG_SHEET, header=0)
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
def get_utilization_overview(ground_truth_long_df: pd.DataFrame) -> dict:
    """
    KPIs/trend/split/ranking for the Utilization Overview page, sourced
    from the ground-truth `Utilization_Long` sheet (NOT re-derived from
    the booking sheet's Formula A) since that sheet already carries the
    precomputed `Period Total Utilization %` per employee that
    `Average Period Utilization %`'s DAX averages over
    (`AVERAGEX(VALUES(Employee), MAX(Period Total Utilization %))`) --
    reusing it here avoids re-deriving a "period" definition that isn't
    specified anywhere else in this codebase.

    Returns:
      {
        "average_period_utilization_pct": float,  # 0-1, matches DAX Average Period Utilization %
        "total_employees": int,                   # distinct employees in Utilization_Long
        "latest_week_utilization_pct": float,      # DAX Latest Week Utilization % (avg of latest week's rows)
        "weekly_trend": [{"week_start": str, "avg_weekly_utilization_pct": float}, ...],
        "utilization_split": {"high": int, "moderate": int, "low": int},  # band counts, one row per employee via Period Total Utilization %
        "employee_ranking": [{"employee": str, "period_utilization_pct": float}, ...],  # desc
      }

    Band thresholds (High >= 0.90, Moderate 0.80-0.90, Low < 0.80) are a
    provisional guess matching the ground-truth sheet's documented
    green/amber color cues (data-model SKILL.md: "green >= ~90%, amber
    ~80%") -- UNCONFIRMED against a real `Utilization Band` DAX formula
    (still missing per that skill's "Flagged discrepancies" section).
    """
    df = ground_truth_long_df.copy()
    df["Week Start"] = pd.to_datetime(df["Week Start"])

    per_employee = df.drop_duplicates("Employee")[["Employee", "Period Total Utilization %"]]
    average_period_pct = float(per_employee["Period Total Utilization %"].mean())

    latest_week = df["Week Start"].max()
    latest_week_pct = float(df.loc[df["Week Start"] == latest_week, "Weekly Utilization %"].mean())

    trend = (
        df.groupby("Week Start")["Weekly Utilization %"]
        .mean()
        .sort_index()
    )
    weekly_trend = [
        {"week_start": week.strftime("%Y-%m-%d"), "avg_weekly_utilization_pct": float(pct)}
        for week, pct in trend.items()
    ]

    def band(pct: float) -> str:
        if pct >= 0.90:
            return "high"
        if pct >= 0.80:
            return "moderate"
        return "low"

    bands = per_employee["Period Total Utilization %"].apply(band).value_counts()
    utilization_split = {
        "high": int(bands.get("high", 0)),
        "moderate": int(bands.get("moderate", 0)),
        "low": int(bands.get("low", 0)),
    }

    ranking = per_employee.sort_values("Period Total Utilization %", ascending=False)
    employee_ranking = [
        {"employee": row["Employee"], "period_utilization_pct": float(row["Period Total Utilization %"])}
        for _, row in ranking.iterrows()
    ]

    return {
        "average_period_utilization_pct": average_period_pct,
        "total_employees": int(df["Employee"].nunique()),
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
