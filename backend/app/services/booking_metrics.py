"""
Aggregation functions over the time-booking sheet (`Sheet1` in the real
Power BI model), sourced from `backend/data/UTILIZATION_DATA_SHEET.xlsx`.

Design notes (per api-conventions SKILL.md "Excel/DB swap boundary"):
- Every public function takes a DataFrame and returns a plain scalar,
  so callers stay stable when the backing store moves to a DB.
- Source column names are kept exactly as they appear in the Excel file.

Per data-model SKILL.md, `Holding` is the clean, one-value-per-row
client field for this sheet — used here instead of the roster's messy
multi-value `Client as on June 2026` column, per that skill's explicit
instruction to prefer this table for per-client metrics.

Utilization-percentage measures (`Weekly Utilization %` and friends) are
OUT OF SCOPE for this module — deferred per data-model SKILL.md pending
an overlapping-week export between the booking sheet and the
ground-truth utilization sheet. Do not add them here without that
reconciliation being unblocked first.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from app.services.cache_utils import cache_on_df

logger = logging.getLogger(__name__)

DEFAULT_BOOKING_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "UTILIZATION DATA SHEET.xlsx"
)

CLIENT_HOURS_LABEL = "Client Hours"
INTERNAL_HOURS_LABEL = "Internal Hours"


def load_booking_data(path: str | Path = DEFAULT_BOOKING_PATH) -> pd.DataFrame:
    """
    Read the booking sheet Excel file, keeping source column names as-is.
    Row count is logged (1523 rows in the source file as of 2026-07-15,
    up from 258/2-weeks in the prior export; now spans 7 distinct
    `Monday of Week` values, 2026-04-13 through 2026-05-25) so silent
    drops during later processing are detectable.

    Data-quality note: the current file has exactly 1 row (index 258)
    that is entirely blank (every column NaN, including `Employee` and
    `Employee Booked Hours`) -- NOT dropped here, since dropping rows in
    the read layer would violate the "never silently drop" rule. It is
    logged as a warning instead; all aggregation functions in this module
    naturally exclude it via pandas' default NaN-exclusion in `.sum()` /
    `.nunique(dropna=True)`, so it does not skew any metric, but a caller
    that iterates raw rows (e.g. building a per-row table) must handle it
    explicitly.
    """
    df = pd.read_excel(path)
    logger.info("load_booking_data: read %d rows from %s", len(df), path)
    blank_mask = df.isna().all(axis=1)
    if blank_mask.any():
        logger.warning(
            "load_booking_data: %d fully-blank row(s) found at index %s -- "
            "not dropped, but excluded naturally by downstream NaN-safe "
            "aggregations (sum/nunique dropna=True)",
            int(blank_mask.sum()),
            df.index[blank_mask].tolist(),
        )
    return df


def prepare_booking_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    One-time cleanup shared by every row-level booking view
    (`get_filtered_records`, `records_to_dicts`, ...): drop the fully-blank
    row and parse `Monday of Week`/`Date` to real datetimes.

    Pulled out of `get_filtered_records` (which used to redo this --
    `.copy()` + two `pd.to_datetime` calls over the whole sheet -- on every
    single request regardless of filters) so `data_loader.py` can compute
    and cache it once per booking-DataFrame load. See
    `data_loader.get_booking_df_prepared`.
    """
    out = df[~df.isna().all(axis=1)].copy()
    out["Monday of Week"] = pd.to_datetime(out["Monday of Week"])
    if "Date" in out.columns:
        out["Date"] = pd.to_datetime(out["Date"])
    return out


def get_total_hours(df: pd.DataFrame) -> float:
    """
    `Total Hours` — sum of `Employee Booked Hours` across all rows
    (both Client Hours and Internal Hours types).
    Reads: `Employee Booked Hours`.
    Edge cases: NaN hours are excluded from the sum by pandas default.
    """
    return float(df["Employee Booked Hours"].sum())


def get_client_hours(df: pd.DataFrame) -> float:
    """
    `Client Hours` — sum of `Employee Booked Hours` where
    `Booked Hours Type` == "Client Hours".
    Reads: `Booked Hours Type`, `Employee Booked Hours`.
    """
    mask = df["Booked Hours Type"] == CLIENT_HOURS_LABEL
    return float(df.loc[mask, "Employee Booked Hours"].sum())


def get_internal_hours(df: pd.DataFrame) -> float:
    """
    `Internal Hours` — sum of `Employee Booked Hours` where
    `Booked Hours Type` == "Internal Hours".
    Reads: `Booked Hours Type`, `Employee Booked Hours`.
    """
    mask = df["Booked Hours Type"] == INTERNAL_HOURS_LABEL
    return float(df.loc[mask, "Employee Booked Hours"].sum())


def get_client_hours_pct(df: pd.DataFrame) -> float:
    """
    `Client Hours %` — Client Hours / Total Hours * 100.
    Reads: `Booked Hours Type`, `Employee Booked Hours`.
    Edge cases: returns 0.0 if Total Hours is 0 (avoids div-by-zero).
    """
    total = get_total_hours(df)
    if total == 0:
        return 0.0
    return get_client_hours(df) / total * 100


def get_internal_hours_pct(df: pd.DataFrame) -> float:
    """
    `Internal Hours %` — Internal Hours / Total Hours * 100.
    Reads: `Booked Hours Type`, `Employee Booked Hours`.
    Edge cases: returns 0.0 if Total Hours is 0.
    """
    total = get_total_hours(df)
    if total == 0:
        return 0.0
    return get_internal_hours(df) / total * 100


def get_total_clients(df: pd.DataFrame) -> int:
    """
    `Total Clients` — count of distinct `Holding` values (per data-model
    SKILL.md, `Holding` is the clean client field for this sheet, not
    the roster's `Client as on June 2026`).
    Reads: `Holding`.
    Edge cases: NaN/blank Holding values are excluded from the distinct
    count via pandas `nunique(dropna=True)` default.
    """
    return int(df["Holding"].nunique(dropna=True))


def get_total_projects(df: pd.DataFrame) -> int:
    """
    `Total Projects` = DISTINCTCOUNT('Sheet1'[Project]).

    COLUMN NAME RESOLVED: the real DAX is written against a column named
    `Project` (`Sheet1[Project]`), but data-model SKILL.md's column
    dictionary documents the booking sheet's column as `Project Name`.
    Checked the actual file (`UTILIZATION_DATA_SHEET.xlsx`) — its columns
    are: Region (EC), Market (EC), Segment (EC), Global Department,
    Department, Team (EC), Holding, Project Name, Project URL, Employee,
    Month, Monday of Week, Date, Booked Hours Type, Employee Booked
    Hours. There is NO column literally named `Project` — only
    `Project Name` exists. Treating `Sheet1[Project]` in the DAX as
    referring to this file's `Project Name` column (the only plausible
    match); flagging the name mismatch here rather than silently
    resolving it as certain, since the live model's exact source column
    was not independently confirmed.
    Reads: `Project Name`.
    Edge cases: NaN/blank Project Name values excluded from the count.
    """
    return int(df["Project Name"].nunique(dropna=True))


def get_total_regions(df: pd.DataFrame) -> int:
    """
    `Total Regions` = DISTINCTCOUNT('Sheet1'[Region (EC)]).
    NEWLY ADDED.
    Reads: `Region (EC)`.
    Edge cases: NaN/blank values excluded from the count.
    """
    return int(df["Region (EC)"].nunique(dropna=True))


def get_total_employees(df: pd.DataFrame) -> int:
    """
    `Total Employeess` (sic — typo preserved verbatim from the real DAX
    measure name per data-model SKILL.md) = DISTINCTCOUNT('Sheet1'[Employee]).
    Reads: `Employee`.
    Edge cases: NaN/blank Employee values excluded from the count.
    """
    return int(df["Employee"].nunique(dropna=True))


def get_weekly_hours_trend(df: pd.DataFrame) -> list[dict]:
    """
    Client Hours vs Internal Hours, summed per `Monday of Week`. Powers
    the Utilization Home page's "Weekly Hours Trend" bar chart.
    Reads: `Monday of Week`, `Booked Hours Type`, `Employee Booked Hours`.
    Edge cases: rows with NaN `Monday of Week` are excluded (groupby
    default dropna=True) — this drops the one fully-blank row noted in
    `load_booking_data`.
    """
    grouped = df.copy()
    grouped["Monday of Week"] = pd.to_datetime(grouped["Monday of Week"])
    pivot = (
        grouped.groupby(["Monday of Week", "Booked Hours Type"])["Employee Booked Hours"]
        .sum()
        .unstack(fill_value=0.0)
        .sort_index()
    )
    if CLIENT_HOURS_LABEL not in pivot.columns:
        pivot[CLIENT_HOURS_LABEL] = 0.0
    if INTERNAL_HOURS_LABEL not in pivot.columns:
        pivot[INTERNAL_HOURS_LABEL] = 0.0
    return [
        {
            "week_start": week.strftime("%Y-%m-%d"),
            "client_hours": float(row[CLIENT_HOURS_LABEL]),
            "internal_hours": float(row[INTERNAL_HOURS_LABEL]),
        }
        for week, row in pivot.iterrows()
    ]


def get_hours_by_region(df: pd.DataFrame) -> list[dict]:
    """
    Total Hours summed per `Region (EC)`. Powers the Utilization Home
    page's "Total Hours by Market/Region" bar chart.
    Reads: `Region (EC)`, `Employee Booked Hours`.
    Edge cases: NaN/blank `Region (EC)` rows excluded (groupby default).
    """
    grouped = (
        df.groupby("Region (EC)")["Employee Booked Hours"]
        .sum()
        .sort_values(ascending=False)
    )
    return [
        {"region": region, "total_hours": float(hours)} for region, hours in grouped.items()
    ]


def get_hours_by_region_market(df: pd.DataFrame) -> list[dict]:
    """
    Total Hours summed per (`Region (EC)`, `Market (EC)`) pair. Powers the
    Utilization Home page's "Total Hours by Market(EC) and Region(EC)" bar
    chart, whose reference x-axis uses combined "Region/Market" labels
    (e.g. "AMER/AMER", "EMEA/BENO", "EMEA/DACH", "EMEA/UKI").

    This is not a named measure in data-model SKILL.md's "Confirmed Power
    BI model structure" section — no single DAX measure combines
    `Region (EC)` and `Market (EC)` into one grouped total. It is a
    best-effort extension of `get_hours_by_region` (itself just
    `Total Hours` grouped by `Region (EC)`) to also group by
    `Market (EC)`, built to match the reference chart's combined-label
    behavior. Flagging as UNCONFIRMED/pending reconciliation against any
    real DAX for this specific chart, per data-model SKILL.md's rule on
    metrics without a shared formula.

    Reads: `Region (EC)`, `Market (EC)`, `Employee Booked Hours`.
    Edge cases: rows with NaN/blank `Region (EC)` or `Market (EC)` are
    excluded (groupby default dropna=True), consistent with
    `get_hours_by_region`.
    """
    grouped = (
        df.groupby(["Region (EC)", "Market (EC)"])["Employee Booked Hours"]
        .sum()
        .sort_values(ascending=False)
    )
    return [
        {"region": region, "market": market, "total_hours": float(hours)}
        for (region, market), hours in grouped.items()
    ]


def get_filter_options(df: pd.DataFrame) -> dict:
    """
    Distinct values for each Search-page filter field, sorted for stable
    dropdown ordering. Powers the Search page's filter form.
    Reads: `Monday of Week`, `Region (EC)`, `Department`, `Team (EC)`,
    `Holding`, `Booked Hours Type`, `Market (EC)`.

    `markets` (`Market (EC)` distinct values, e.g. `Technology`, `BN`,
    `DACH`, `UKI` — see `get_hours_by_region_market`'s docstring for the
    label caveat) was ADDED so the Region/Market filter can be genuinely
    hierarchical, not just cosmetic.
    """
    weeks = pd.to_datetime(df["Monday of Week"].dropna().unique())
    return {
        "weeks": sorted(w.strftime("%Y-%m-%d") for w in weeks),
        "regions": sorted(df["Region (EC)"].dropna().unique().tolist()),
        "markets": sorted(df["Market (EC)"].dropna().unique().tolist()),
        "departments": sorted(df["Department"].dropna().unique().tolist()),
        "entities": sorted(df["Team (EC)"].dropna().unique().tolist()),
        "holdings": sorted(df["Holding"].dropna().unique().tolist()),
        "hours_types": sorted(df["Booked Hours Type"].dropna().unique().tolist()),
    }


def _matches_any(series: pd.Series, values: list[str] | None) -> pd.Series:
    """
    Build a boolean mask for "column value is in the given list", used to
    give each filter field OR-within-field semantics for
    `get_filtered_records`'s multi-value filters. Returns an all-True mask
    (no-op) if `values` is falsy (`None` or empty list).
    """
    if not values:
        return pd.Series(True, index=series.index)
    return series.isin(values)


def get_filtered_records(
    df: pd.DataFrame,
    week: str | list[str] | None = None,
    region: str | list[str] | None = None,
    market: str | list[str] | None = None,
    department: str | list[str] | None = None,
    entity: str | list[str] | None = None,
    holding: str | list[str] | None = None,
    hours_type: str | list[str] | None = None,
) -> pd.DataFrame:
    """
    Apply the Search page's filter set to the booking sheet and return the
    matching rows (unpaginated — callers slice for `limit`/`offset`).
    Reads: `Monday of Week`, `Region (EC)`, `Market (EC)`, `Department`,
    `Team (EC)`, `Holding`, `Booked Hours Type`, plus whatever columns the
    caller projects afterward.

    Each filter accepts either a single string (backward-compatible) or a
    list of strings — matching is OR within a field (row matches if its
    value is any of the given values) and AND across different fields
    (e.g. `region IN (EMEA, AMER) AND hours_type IN (Client Hours)`).
    Edge cases: any filter left as `None` or an empty list is not applied
    (no-op), so calling with no args returns every row unfiltered.

    Also excludes the source file's fully-blank row(s) (every column NaN
    -- see `load_booking_data`'s docstring) from the returned rows. That
    row is already naturally excluded from SUM/nunique-based aggregations
    elsewhere in this module, but row-level listing (this function, and
    `records_to_dicts` downstream of it) needs an explicit exclusion or
    it surfaces as a ghost all-blank record. `load_booking_data`'s own
    blank-row logging is untouched -- this only affects what this
    function returns, not whether the row's presence is logged.
    """
    # `df` is normally already `data_loader.get_booking_df_prepared()`
    # (blank row dropped, dates parsed) -- these checks make this function
    # idempotent/cheap to call again on an already-prepared frame (e.g.
    # from tests that pass the raw df), without redoing the parse on every
    # request in the common case.
    out = df if ~df.isna().all(axis=1).any() else df[~df.isna().all(axis=1)]
    if not pd.api.types.is_datetime64_any_dtype(out["Monday of Week"]):
        out = out.copy()
        out["Monday of Week"] = pd.to_datetime(out["Monday of Week"])

    def _as_list(v: str | list[str] | None) -> list[str] | None:
        if v is None:
            return None
        return [v] if isinstance(v, str) else list(v)

    weeks = _as_list(week)
    if weeks:
        out = out[out["Monday of Week"].isin(pd.to_datetime(weeks))]
    out = out[_matches_any(out["Region (EC)"], _as_list(region))]
    out = out[_matches_any(out["Market (EC)"], _as_list(market))]
    out = out[_matches_any(out["Department"], _as_list(department))]
    out = out[_matches_any(out["Team (EC)"], _as_list(entity))]
    out = out[_matches_any(out["Holding"], _as_list(holding))]
    out = out[_matches_any(out["Booked Hours Type"], _as_list(hours_type))]
    return out


def get_holdings_with_projects(df: pd.DataFrame) -> list[dict]:
    """
    Static holding -> distinct project-name list, for populating the
    filter dropdown's holding->project hierarchy without the caller having
    to fetch every row and group client-side.

    Not a named DAX measure — a lightweight groupby convenience over
    `Holding` / `Project Name`, matching the pairing already implied by
    one row per employee/project/day in the booking sheet.

    Reads: `Holding`, `Project Name`.
    Edge cases: rows with NaN/blank `Holding` are excluded (groupby
    default dropna=True); NaN `Project Name` values within a holding's
    group are dropped before building that holding's project list.
    Holdings are sorted alphabetically; each holding's project list is
    also sorted alphabetically for stable output.
    """
    grouped = df.dropna(subset=["Holding"]).groupby("Holding")["Project Name"]
    items = []
    for holding, projects in grouped:
        project_list = sorted(projects.dropna().unique().tolist())
        items.append({"holding": holding, "projects": project_list})
    items.sort(key=lambda item: item["holding"])
    return items


def get_records_summary(df: pd.DataFrame) -> dict:
    """
    Summary KPIs for a (typically filtered) slice of the booking sheet —
    Total/Client/Internal Hours, Total Projects, Average Hours. Powers the
    Results page's summary strip above the paginated table.
    Reads: `Booked Hours Type`, `Employee Booked Hours`, `Project Name`.
    """
    total_hours = get_total_hours(df)
    return {
        "total_hours": total_hours,
        "client_hours": get_client_hours(df),
        "internal_hours": get_internal_hours(df),
        "total_projects": get_total_projects(df),
        "average_hours": float(df["Employee Booked Hours"].mean()) if len(df) else 0.0,
    }


def records_to_dicts(df: pd.DataFrame) -> list[dict]:
    """
    Project a (filtered) booking-sheet slice into the row shape the
    Results page's table needs: Week Start, Date, Employee, Project,
    Holding, hours, hours type, plus Region/Department/Team for the
    reference table's org-hierarchy columns.
    Reads: `Monday of Week`, `Date`, `Employee`, `Project Name`,
    `Holding`, `Booked Hours Type`, `Employee Booked Hours`,
    `Region (EC)`, `Department`, `Team (EC)`.
    """
    out = df.copy()
    out["Monday of Week"] = pd.to_datetime(out["Monday of Week"])
    out["Date"] = pd.to_datetime(out["Date"])
    records = []
    for _, row in out.iterrows():
        records.append(
            {
                "week_start": row["Monday of Week"].strftime("%Y-%m-%d")
                if pd.notna(row["Monday of Week"])
                else None,
                "date": row["Date"].strftime("%Y-%m-%d") if pd.notna(row["Date"]) else None,
                "employee": row["Employee"] if pd.notna(row["Employee"]) else None,
                "project": row["Project Name"] if pd.notna(row["Project Name"]) else None,
                "holding": row["Holding"] if pd.notna(row["Holding"]) else None,
                "hours_type": row["Booked Hours Type"]
                if pd.notna(row["Booked Hours Type"])
                else None,
                "hours": float(row["Employee Booked Hours"])
                if pd.notna(row["Employee Booked Hours"])
                else 0.0,
                "region": row["Region (EC)"] if pd.notna(row["Region (EC)"]) else None,
                "department": row["Department"] if pd.notna(row["Department"]) else None,
                "team": row["Team (EC)"] if pd.notna(row["Team (EC)"]) else None,
            }
        )
    return records


def get_employee_detail(df: pd.DataFrame, employee: str) -> dict | None:
    """
    Per-employee drill-through for the Employee Utilization page: Total/
    Client/Internal Hours, Total Projects, Total Hours by Project, Total
    Hours by Week Start + Hours Type.
    Reads: `Employee`, `Booked Hours Type`, `Employee Booked Hours`,
    `Project Name`, `Monday of Week`.
    Edge cases: returns None if `employee` has no rows at all (e.g. the
    unresolved `Amit Singh`/`Ankit Singh` name-variant case per
    data-model SKILL.md — callers should 404, not crash, on None).
    """
    rows = df[df["Employee"] == employee]
    if rows.empty:
        return None

    by_project = (
        rows.groupby("Project Name")["Employee Booked Hours"].sum().sort_values(ascending=False)
    )
    hours_by_project = [
        {"project": project, "total_hours": float(hours)}
        for project, hours in by_project.items()
    ]

    weekly = rows.copy()
    weekly["Monday of Week"] = pd.to_datetime(weekly["Monday of Week"])
    pivot = (
        weekly.groupby(["Monday of Week", "Booked Hours Type"])["Employee Booked Hours"]
        .sum()
        .unstack(fill_value=0.0)
        .sort_index()
    )
    if CLIENT_HOURS_LABEL not in pivot.columns:
        pivot[CLIENT_HOURS_LABEL] = 0.0
    if INTERNAL_HOURS_LABEL not in pivot.columns:
        pivot[INTERNAL_HOURS_LABEL] = 0.0
    hours_by_week = [
        {
            "week_start": week.strftime("%Y-%m-%d"),
            "client_hours": float(row[CLIENT_HOURS_LABEL]),
            "internal_hours": float(row[INTERNAL_HOURS_LABEL]),
        }
        for week, row in pivot.iterrows()
    ]

    return {
        "employee": employee,
        "total_hours": get_total_hours(rows),
        "client_hours": get_client_hours(rows),
        "internal_hours": get_internal_hours(rows),
        "total_projects": get_total_projects(rows),
        "hours_by_project": hours_by_project,
        "hours_by_week": hours_by_week,
    }


def get_project_detail(df: pd.DataFrame, holding: str) -> dict | None:
    """
    Per-project/holding drill-through for the Project Utilization page:
    Total Hours by Employee + Hours Type, Total Hours by Week Start +
    Hours Type, plus a detail table (Employee, Project, Region,
    Department).
    Reads: `Holding`, `Employee`, `Booked Hours Type`,
    `Employee Booked Hours`, `Monday of Week`, `Project Name`,
    `Region (EC)`, `Department`.
    Edge cases: returns None if `holding` has no rows at all.
    """
    rows = df[df["Holding"] == holding]
    if rows.empty:
        return None

    by_employee = rows.copy()
    by_employee["Monday of Week"] = pd.to_datetime(by_employee["Monday of Week"])
    emp_pivot = (
        by_employee.groupby(["Employee", "Booked Hours Type"])["Employee Booked Hours"]
        .sum()
        .unstack(fill_value=0.0)
    )
    if CLIENT_HOURS_LABEL not in emp_pivot.columns:
        emp_pivot[CLIENT_HOURS_LABEL] = 0.0
    if INTERNAL_HOURS_LABEL not in emp_pivot.columns:
        emp_pivot[INTERNAL_HOURS_LABEL] = 0.0
    hours_by_employee = [
        {
            "employee": employee,
            "client_hours": float(row[CLIENT_HOURS_LABEL]),
            "internal_hours": float(row[INTERNAL_HOURS_LABEL]),
        }
        for employee, row in emp_pivot.iterrows()
    ]

    week_pivot = (
        by_employee.groupby(["Monday of Week", "Booked Hours Type"])["Employee Booked Hours"]
        .sum()
        .unstack(fill_value=0.0)
        .sort_index()
    )
    if CLIENT_HOURS_LABEL not in week_pivot.columns:
        week_pivot[CLIENT_HOURS_LABEL] = 0.0
    if INTERNAL_HOURS_LABEL not in week_pivot.columns:
        week_pivot[INTERNAL_HOURS_LABEL] = 0.0
    hours_by_week = [
        {
            "week_start": week.strftime("%Y-%m-%d"),
            "client_hours": float(row[CLIENT_HOURS_LABEL]),
            "internal_hours": float(row[INTERNAL_HOURS_LABEL]),
        }
        for week, row in week_pivot.iterrows()
    ]

    detail_rows = rows[["Employee", "Project Name", "Region (EC)", "Department"]].drop_duplicates()
    detail = [
        {
            "employee": row["Employee"],
            "project": row["Project Name"],
            "region": row["Region (EC)"],
            "department": row["Department"],
        }
        for _, row in detail_rows.iterrows()
    ]

    return {
        "holding": holding,
        "total_hours": get_total_hours(rows),
        "client_hours": get_client_hours(rows),
        "internal_hours": get_internal_hours(rows),
        "hours_by_employee": hours_by_employee,
        "hours_by_week": hours_by_week,
        "detail": detail,
    }


def get_markets_covered(df: pd.DataFrame) -> int:
    """
    `Markets Covered` = DISTINCTCOUNT('Sheet1'[Market (EC)]).
    NEWLY ADDED. Note: `Markets Covered` also appears as a name in the
    `HR MASTER` measure list in data-model SKILL.md's "Confirmed Power BI
    model structure" section, but the DAX provided targets
    `Sheet1[Market (EC)]` (the booking sheet), so this is implemented
    here in booking_metrics.py, not roster_metrics.py.
    Reads: `Market (EC)`.
    Edge cases: NaN/blank values excluded from the count.
    """
    return int(df["Market (EC)"].nunique(dropna=True))
