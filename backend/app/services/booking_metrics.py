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
computed here via the config-driven `ratio_by`/`ratio_bands` chart types
(see `evaluate_booking_card`/`evaluate_booking_chart` below) using
Formula A — `Client Hours / (Client Hours + Internal Hours)` — the only
data source is this booking sheet.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from app.services import metric_config
from app.services.cache_utils import cache_on_df

logger = logging.getLogger(__name__)

DEFAULT_BOOKING_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "UTILIZATION DATA SHEET.xlsx"
)

# Sourced from configs/booking_metrics.yaml so a relabelled or added hours
# category is a config edit, not a code change. The
# `hours_split_covers_all_hours` invariant catches a new category that
# these two labels would otherwise silently exclude from the donut.
CLIENT_HOURS_LABEL = metric_config.client_hours_label()
INTERNAL_HOURS_LABEL = metric_config.internal_hours_label()


# ---------------------------------------------------------------------------
# Config-driven KPI / chart dispatchers (Phase 2 — Utilization Home).
# ---------------------------------------------------------------------------
# Mirrors the roster's `evaluate_card` / `evaluate_chart`: the values on
# screen come from the DECLARATION in `configs/booking_metrics.yaml`, not
# a bespoke function per KPI. Every public `get_*` below now routes
# through one of these two entry points, so a card/chart is a config
# edit rather than a code + test change.

def evaluate_booking_card(df: pd.DataFrame, card_name: str) -> float | int:
    """
    Compute a Utilization-side KPI straight from its declaration in
    `configs/booking_metrics.yaml` under `cards:`.

    Supported today:
      * measure_type: `distinct_count` — nunique over the declared column
        (dropna default, matches DAX DISTINCTCOUNT semantics)
      * measure_type: `sum` — sum over the declared column, optionally
        narrowed by `filter_column_role == hours[filter_label_key]`
      * measure_type: `count_rows` — plain row count over the (optionally
        filtered) frame

    Same design contract as the roster's `evaluate_card`: the declaration
    is authoritative rather than merely documentary. Pointing a card at a
    different column role changes the number on screen — no Python edit.
    """
    spec = metric_config.booking_card(card_name)
    measure_type = spec.get("measure_type", "distinct_count")
    # `column_role` is required for the column-based primitives
    # (distinct_count / sum / count_rows / mean); `ratio` and
    # `avg_of_chart` declare their own role set (numerator/denominator, or
    # from_chart) so this resolution is skipped for them and each branch
    # below reads the specific fields it needs. Same guard shape as
    # `validate_metric_config`'s column_role precheck.
    if measure_type in ("ratio", "avg_of_chart"):
        column = None  # unused for these branches
    else:
        column = metric_config.booking_column(spec["column_role"])

    scope = df
    filter_role = spec.get("filter_column_role")
    if filter_role is not None:
        filter_col = metric_config.booking_column(filter_role)
        filter_value = metric_config.hours_label(spec["filter_label_key"])
        scope = scope[scope[filter_col] == filter_value]
    if measure_type == "distinct_count":
        return int(scope[column].nunique(dropna=True))
    if measure_type == "sum":
        return float(scope[column].sum())
    if measure_type == "count_rows":
        return int(len(scope))
    if measure_type == "mean":
        # Powers the `average_hours` card on the Utilization Results page:
        # pandas .mean() on an empty Series returns NaN, but the endpoint
        # response model wants a plain float and the KPI card would render
        # "NaN" — coerce that back to 0.0 to match get_records_summary's
        # existing empty-frame contract (see its test_get_records_summary_empty).
        if len(scope) == 0:
            return 0.0
        value = float(scope[column].mean())
        return 0.0 if pd.isna(value) else value
    if measure_type == "ratio":
        # Generic Formula-A-shaped primitive: sum(numerator) / sum(denominator),
        # each side optionally narrowed by a Booked-Hours-Type-style filter.
        # Introduced for the Overview page's booking-derived KPIs — the
        # ground-truth file is no longer consulted at runtime.
        num_col = metric_config.booking_column(spec["numerator_column_role"])
        den_col = metric_config.booking_column(spec["denominator_column_role"])
        num_scope = scope
        if spec.get("numerator_filter_column_role"):
            fcol = metric_config.booking_column(spec["numerator_filter_column_role"])
            fval = metric_config.hours_label(spec["numerator_filter_label_key"])
            num_scope = num_scope[num_scope[fcol] == fval]
        den_scope = scope
        if spec.get("denominator_filter_column_role"):
            fcol = metric_config.booking_column(spec["denominator_filter_column_role"])
            fval = metric_config.hours_label(spec["denominator_filter_label_key"])
            den_scope = den_scope[den_scope[fcol] == fval]
        denom = float(den_scope[den_col].sum())
        if denom == 0:
            return 0.0
        return float(num_scope[num_col].sum()) / denom
    if measure_type == "avg_of_chart":
        # Mean over the values of a declared chart's output — used for the
        # Overview "Average Period Utilization %" KPI so the headline can't
        # drift from the Employee Ranking chart it summarizes (both go
        # through the SAME chart declaration). Optional
        # `scope_to_latest_of_role` narrows the frame to rows whose role
        # column equals its max first — used by "Latest Week Utilization %".
        from_chart_name = spec["from_chart"]
        chart_scope = scope
        latest_role = spec.get("scope_to_latest_of_role")
        if latest_role is not None:
            latest_col = metric_config.booking_column(latest_role)
            if chart_scope[latest_col].notna().any():
                latest_value = chart_scope[latest_col].max()
                chart_scope = chart_scope[chart_scope[latest_col] == latest_value]
        values = evaluate_booking_chart(chart_scope, from_chart_name)
        if isinstance(values, dict):
            nums = [float(v) for v in values.values() if pd.notna(v)]
        else:
            # ratio_bands returns a dict-of-counts, list, or DataFrame; we
            # only compose avg_of_chart with a ratio_by (validator enforces
            # via from_chart -> chart type indirection is upstream).
            nums = []
        if not nums:
            return 0.0
        return float(sum(nums) / len(nums))
    # Guarded by the config validator — reaching this means the validator
    # missed a case, which is a developer error, not user data.
    raise ValueError(
        f"Card {card_name!r} declares unsupported measure_type={measure_type!r}"
    )


def evaluate_booking_chart(df: pd.DataFrame, chart_name: str):
    """
    Compute a Utilization-side chart straight from its declaration in
    `configs/booking_metrics.yaml` under `charts:`.

    Supported types:
      * `sum_by` (no split): {group_value: total} dict
      * `sum_by` (with `split_column_role`): a pivot table returned as
        a list of dicts, one per group, keyed by the group column + each
        split-value
      * `sum_by_hierarchical`: list of {primary, secondary, value} dicts,
        sorted by value descending

    Every chart on the Utilization Home page goes through this.
    """
    spec = metric_config.booking_chart(chart_name)
    kind = spec["type"]
    # `value_column_role` is required for the sum-based chart types
    # (`sum_by`, `sum_by_hierarchical`, `sum_by_split`); `ratio_by` and
    # `ratio_bands` read their own role set (numerator/denominator or
    # ratio_from_chart) so this is not resolved for them.
    if kind in ("ratio_by", "ratio_bands", "avg_of_group_ratios"):
        value_col = None  # unused for these branches
    else:
        value_col = metric_config.booking_column(spec["value_column_role"])

    if kind == "sum_by":
        group_col = metric_config.booking_column(spec["group_column_role"])
        split_role = spec.get("split_column_role")
        if split_role is None:
            grouped = df.groupby(group_col, dropna=True)[value_col].sum()
            return {str(k): float(v) for k, v in grouped.items()}
        # Split pivot — one row per group, columns = distinct split values.
        split_col = metric_config.booking_column(split_role)
        pivot = (
            df.groupby([group_col, split_col], dropna=True)[value_col]
            .sum()
            .unstack(fill_value=0.0)
            .sort_index()
        )
        return pivot  # let the caller shape it — different pages need
                     # different projections (see `get_weekly_hours_trend`).

    if kind == "sum_by_hierarchical":
        primary_col = metric_config.booking_column(spec["primary_group_role"])
        secondary_col = metric_config.booking_column(spec["secondary_group_role"])
        grouped = (
            df.groupby([primary_col, secondary_col], dropna=True)[value_col]
            .sum()
            .sort_values(ascending=False)
        )
        return [
            {"primary": str(p), "secondary": str(s), "value": float(v)}
            for (p, s), v in grouped.items()
        ]

    if kind == "sum_by_split":
        # Same math as `sum_by` with a `split_column_role`, but returns the
        # projected `list[{group, <split_value_1>: v, <split_value_2>: v, ...}]`
        # shape rather than the raw pivot table — so the endpoint hands it
        # straight to the response model. `sum_by` deliberately keeps its
        # raw pivot return because the Utilization Home Weekly Hours Trend
        # already projects it into a bespoke shape.
        group_col = metric_config.booking_column(spec["group_column_role"])
        split_col = metric_config.booking_column(spec["split_column_role"])
        pivot = (
            df.groupby([group_col, split_col], dropna=True)[value_col]
            .sum()
            .unstack(fill_value=0.0)
            .sort_index()
        )
        return [
            {"group": str(idx), **{str(c): float(v) for c, v in row.items()}}
            for idx, row in pivot.iterrows()
        ]

    if kind == "ratio_by":
        # Aggregate-then-ratio per group: sum(num)/sum(denom) within each
        # group. Backs the Overview page's Weekly Utilization Trend and
        # Employee Period Utilization ranking (Formula A). A group whose
        # denominator sums to 0 is DROPPED (undefined utilization) rather
        # than reported as 0% — same convention as
        # `utilization_metrics.compute_weekly_utilization_formula_a`.
        group_col = metric_config.booking_column(spec["group_column_role"])
        num_col = metric_config.booking_column(spec["numerator_column_role"])
        den_col = metric_config.booking_column(spec["denominator_column_role"])
        num_scope = df
        if spec.get("numerator_filter_column_role"):
            fcol = metric_config.booking_column(spec["numerator_filter_column_role"])
            fval = metric_config.hours_label(spec["numerator_filter_label_key"])
            num_scope = num_scope[num_scope[fcol] == fval]
        den_scope = df
        if spec.get("denominator_filter_column_role"):
            fcol = metric_config.booking_column(spec["denominator_filter_column_role"])
            fval = metric_config.hours_label(spec["denominator_filter_label_key"])
            den_scope = den_scope[den_scope[fcol] == fval]
        num_by = num_scope.groupby(group_col, dropna=True)[num_col].sum()
        den_by = den_scope.groupby(group_col, dropna=True)[den_col].sum()
        out: dict[str, float] = {}
        for key in den_by.index:
            denom = float(den_by.loc[key])
            if denom == 0:
                continue  # undefined utilization
            numer = float(num_by.get(key, 0.0))
            out[str(key)] = numer / denom
        return out

    if kind == "avg_of_group_ratios":
        # For each outer_group value, compute a ratio_by(inner_group) on
        # that subframe and return the MEAN of those per-inner-group
        # ratios. D1a semantics for the Weekly Utilization Trend chart:
        # mean of per-employee-in-week ratios, per week. A subframe with
        # no defined ratios (every employee has denom=0) is dropped from
        # the output rather than reported as 0 (undefined utilization).
        outer_col = metric_config.booking_column(spec["outer_group_role"])
        inner_col = metric_config.booking_column(spec["inner_group_role"])
        num_col = metric_config.booking_column(spec["numerator_column_role"])
        den_col = metric_config.booking_column(spec["denominator_column_role"])
        num_filter_col = num_filter_val = None
        if spec.get("numerator_filter_column_role"):
            num_filter_col = metric_config.booking_column(spec["numerator_filter_column_role"])
            num_filter_val = metric_config.hours_label(spec["numerator_filter_label_key"])
        den_filter_col = den_filter_val = None
        if spec.get("denominator_filter_column_role"):
            den_filter_col = metric_config.booking_column(spec["denominator_filter_column_role"])
            den_filter_val = metric_config.hours_label(spec["denominator_filter_label_key"])

        out: dict[str, float] = {}
        for outer_val, subframe in df.groupby(outer_col, dropna=True):
            num_scope = subframe
            if num_filter_col is not None:
                num_scope = num_scope[num_scope[num_filter_col] == num_filter_val]
            den_scope = subframe
            if den_filter_col is not None:
                den_scope = den_scope[den_scope[den_filter_col] == den_filter_val]
            num_by = num_scope.groupby(inner_col, dropna=True)[num_col].sum()
            den_by = den_scope.groupby(inner_col, dropna=True)[den_col].sum()
            per_inner = []
            for inner_key in den_by.index:
                denom = float(den_by.loc[inner_key])
                if denom == 0:
                    continue
                per_inner.append(float(num_by.get(inner_key, 0.0)) / denom)
            if per_inner:
                out[str(outer_val)] = sum(per_inner) / len(per_inner)
        return out

    if kind == "ratio_bands":
        ratio_values = evaluate_booking_chart(df, spec["ratio_from_chart"])
        # `ratio_values` is a {group: ratio} dict from the underlying
        # `ratio_by`. Bin each ratio into the first matching band (`below`
        # wins first, catch-all last band has no `below`).
        counts: dict[str, int] = {b["label"]: 0 for b in spec["bands"]}
        for value in ratio_values.values():
            for band in spec["bands"]:
                if "below" not in band or value < band["below"]:
                    counts[band["label"]] += 1
                    break
        return counts

    raise ValueError(f"Chart {chart_name!r} declares unsupported type={kind!r}")


def load_booking_data(path: str | Path = DEFAULT_BOOKING_PATH) -> pd.DataFrame:
    """
    Read the booking sheet Excel file, keeping source column names as-is.
    Row count is logged (1522 rows in the source file as of 2026-07-17,
    up from 258/2-weeks in the original export; now spans 7 distinct
    `Monday of Week` values, 2026-04-13 through 2026-05-25) so silent
    drops during later processing are detectable.

    Data-quality note: two separate fully/partially-blank rows have been
    found and deleted from the source file so far, on two different
    dates (2026-07-16, then a different row on 2026-07-17 -- see the
    data-model skill for both). Each was removed directly from the Excel
    file with a backup taken first (`backend/data/backups/`), rather
    than left in and filtered downstream, so the row count above may
    still shift if a future data refresh reintroduces something similar.
    The blank-row detection/logging code below is left in place as a
    harmless safety net (it will simply log nothing and no-op on a clean
    file) rather than removed, matching how the other source-data fixes
    in this codebase keep their normalization/detection code as a safety
    net rather than deleting it. `prepare_booking_df` (below) is the
    stronger, generalized guard — it drops any row with no `Employee`,
    which is what actually protects row-level API responses.
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
    (`get_filtered_records`, `records_to_dicts`, ...): drop any row with no
    `Employee` and parse `Monday of Week`/`Date` to real datetimes.

    Data-quality note: a booking row with a blank `Employee` carries no
    attributable data regardless of what else is populated (see the
    2026-07-17 row that had only `Project URL` filled in — every
    aggregation elsewhere in this module already excludes NaN `Employee`
    via `dropna=True`, but the raw row-level views did not, which is what
    let that row reach the frontend and crash pages that group by
    `employee`/`holding` without a null guard). Filtering on `Employee`
    here also covers the previously-separate fully-blank-row case, since
    a fully-blank row has a NaN `Employee` too.

    Pulled out of `get_filtered_records` (which used to redo this --
    `.copy()` + two `pd.to_datetime` calls over the whole sheet -- on every
    single request regardless of filters) so `data_loader.py` can compute
    and cache it once per booking-DataFrame load. See
    `data_loader.get_booking_df_prepared`.
    """
    dropped = df["Employee"].isna()
    if dropped.any():
        logger.warning(
            "prepare_booking_df: dropping %d row(s) with no Employee at index %s",
            int(dropped.sum()),
            df.index[dropped].tolist(),
        )
    out = df[~dropped].copy()
    out["Monday of Week"] = pd.to_datetime(out["Monday of Week"])
    if "Date" in out.columns:
        out["Date"] = pd.to_datetime(out["Date"])
    return out


def get_total_hours(df: pd.DataFrame) -> float:
    """
    `Total Hours` — sum of `Employee Booked Hours` across all rows
    (both Client Hours and Internal Hours types). Declared as the
    `total_hours` card in `configs/booking_metrics.yaml`.
    Reads: `Employee Booked Hours`.
    Edge cases: NaN hours are excluded from the sum by pandas default.
    """
    return float(evaluate_booking_card(df, "total_hours"))


def get_client_hours(df: pd.DataFrame) -> float:
    """
    `Client Hours` — sum of `Employee Booked Hours` where
    `Booked Hours Type` == "Client Hours". Declared as the `client_hours`
    card in `configs/booking_metrics.yaml`.
    Reads: `Booked Hours Type`, `Employee Booked Hours`.
    """
    return float(evaluate_booking_card(df, "client_hours"))


def get_internal_hours(df: pd.DataFrame) -> float:
    """
    `Internal Hours` — sum of `Employee Booked Hours` where
    `Booked Hours Type` == "Internal Hours". Declared as the
    `internal_hours` card in `configs/booking_metrics.yaml`.
    Reads: `Booked Hours Type`, `Employee Booked Hours`.
    """
    return float(evaluate_booking_card(df, "internal_hours"))


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

    Declared as the `total_projects` card in configs/booking_metrics.yaml,
    which pins the physical column via the `project` column role — swap
    that role's mapping if a real `Project` column ever appears.
    """
    return int(evaluate_booking_card(df, "total_projects"))


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

    Declared as the `total_employees_booking` card in
    `configs/booking_metrics.yaml`. This DIFFERS by construction from the
    roster's `total_employees` card (distinct NEW_EMP_ID over the whole
    workforce file): booking only sees employees who booked hours, so it
    is a subset of the roster count. A booking-only Employee absent from
    the roster surfaces as a cross-dataset upload WARNING
    (`cross_dataset._unmatched_warning_check("Employee", "roster", ...)`)
    but never blocks the upload — see METRICS.md Page 7.
    """
    return int(evaluate_booking_card(df, "total_employees_booking"))


@cache_on_df
def get_weekly_hours_trend(df: pd.DataFrame) -> list[dict]:
    """
    Client Hours vs Internal Hours, summed per `Monday of Week`. Powers
    the Utilization Home page's "Weekly Hours Trend" bar chart. Declared
    as the `weekly_hours_trend` chart in `configs/booking_metrics.yaml`
    (a `sum_by` with `split_column_role: hours_type`).
    Reads: `Monday of Week`, `Booked Hours Type`, `Employee Booked Hours`.
    Edge cases: rows with NaN `Monday of Week` are excluded (groupby
    default dropna=True) — this drops the one fully-blank row noted in
    `load_booking_data`.
    """
    # `evaluate_booking_chart` returns the raw pivot table for a `sum_by`
    # with a split; this function projects it into the {week_start,
    # client_hours, internal_hours} shape the endpoint's response model
    # expects. Date parsing happens up front so `groupby` sees real
    # Timestamps regardless of what dtype the caller passes in.
    grouped = df.copy()
    grouped["Monday of Week"] = pd.to_datetime(grouped["Monday of Week"])
    pivot = evaluate_booking_chart(grouped, "weekly_hours_trend")
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


@cache_on_df
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


@cache_on_df
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

    Declared as the `total_hours_by_region_market` chart in
    `configs/booking_metrics.yaml` (type `sum_by_hierarchical`). The
    dispatcher returns {primary, secondary, value} tuples; this function
    just renames the keys into the response model's {region, market,
    total_hours} shape.
    """
    return [
        {"region": row["primary"], "market": row["secondary"], "total_hours": row["value"]}
        for row in evaluate_booking_chart(df, "total_hours_by_region_market")
    ]


def _clean_str(value) -> str | None:
    """Normalize a cell to a stripped non-empty string, or None if blank/NaN."""
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    s = str(value).strip()
    return s if s else None


def get_filter_options(df: pd.DataFrame, roster_df: pd.DataFrame | None = None) -> dict:
    """
    Distinct values for each Search-page filter field, sorted for stable
    dropdown ordering. Powers the Search / Results / Utilization Home
    filter forms.

    Reads (booking): `Monday of Week`, `Month`, `Region (EC)`, `Department`,
    `Team (EC)`, `Holding`, `Booked Hours Type`, `Market (EC)`.
    Reads (roster, optional): `Region`, `Market`.

    Canonical source per field (Phase 1 filter-overhaul decision,
    2026-07-23):

    - `regions`, `markets`, `region_market_hierarchy`, `departments` —
      UNION of roster + booking. The roster is the master workforce
      taxonomy per the data-model skill; a value that exists in the
      roster but not in the booking sheet still appears in the filter
      so the user can see every real value (it will filter to zero
      booking rows if picked — that's acceptable and matches user
      intent). Blank/NaN/whitespace-only values are dropped.
      - Region source columns: roster `Region`, booking `Region (EC)`.
      - Market source columns: roster `Market`, booking `Market (EC)`.
      - Department source columns: roster `Designation` (the roster's
        canonical department column — the "Departments" DAX measure is
        `DISTINCTCOUNT(HR MASTER[Designation])`, confirmed in the
        data-model skill and cross-referenced in `docs/METRICS.md`
        under "Card: Departments"), booking `Department`.

    - `entities`, `holdings`, `hours_types` — BOOKING-ONLY. These are
      booking-specific concepts (Team (EC) codes, client holdings,
      Client vs Internal hours) with no roster counterpart, so unioning
      would introduce nothing.

    See `docs/FILTERS.md` for the full canonical-source table and
    rationale.
    """
    weeks = pd.to_datetime(df["Monday of Week"].dropna().unique())
    # Year > Month > Week hierarchy for the cascading date filter. Month is
    # the booking sheet's own `Month` label (authoritative — see
    # WeekHierarchyEntry); year comes from the week's Monday date. Each week
    # maps to exactly one Month in the data, so this nests strictly.
    #
    # `Month` in real xlsx uploads is a datetime cell (pandas reads it as
    # Timestamp); in older/curated fixtures it can be a plain string like
    # "May 26". Format Timestamps as `%b %y` so both shapes converge on the
    # same label. If the cell is missing/NaN, fall back to the week's own
    # Monday-derived month so the entry still lands in a sensible bucket.
    wk = df[["Monday of Week", "Month"]].dropna(subset=["Monday of Week"]).copy()
    wk["Monday of Week"] = pd.to_datetime(wk["Monday of Week"])
    seen: dict[str, dict] = {}
    for monday, month in zip(wk["Monday of Week"], wk["Month"]):
        week_str = monday.strftime("%Y-%m-%d")
        if week_str not in seen:
            if pd.isna(month):
                month_label = monday.strftime("%b %y")
            elif isinstance(month, pd.Timestamp):
                month_label = month.strftime("%b %y")
            else:
                month_label = str(month).strip()
            seen[week_str] = {
                "year": str(monday.year),
                "month": month_label,
                "week": week_str,
            }
    week_hierarchy = sorted(seen.values(), key=lambda e: e["week"])

    # Union region -> {markets} across booking (`Region (EC)`/`Market (EC)`)
    # and, if provided, roster (`Region`/`Market`). A region seen in EITHER
    # source appears in the hierarchy; markets under it are the union of
    # both sources. See docstring above for rationale.
    region_markets: dict[str, set[str]] = {}

    def _absorb(pairs_df: pd.DataFrame, region_col: str, market_col: str) -> None:
        if region_col not in pairs_df.columns:
            return
        for r_raw, m_raw in zip(pairs_df[region_col], pairs_df.get(market_col, [])):
            region = _clean_str(r_raw)
            if region is None:
                continue
            region_markets.setdefault(region, set())
            market = _clean_str(m_raw)
            if market is not None:
                region_markets[region].add(market)

    _absorb(df, "Region (EC)", "Market (EC)")
    if roster_df is not None:
        _absorb(roster_df, "Region", "Market")

    region_market_hierarchy = [
        {"region": r, "markets": sorted(region_markets[r])}
        for r in sorted(region_markets)
    ]

    def _union_clean(*columns: pd.Series) -> list[str]:
        """Union non-blank string values across the given Series, sorted."""
        merged: set[str] = set()
        for series in columns:
            for v in series:
                cleaned = _clean_str(v)
                if cleaned is not None:
                    merged.add(cleaned)
        return sorted(merged)

    # regions: UNION of roster.Region + booking.Region (EC). Flat list kept
    # alongside `region_market_hierarchy` for callers (Search/Results pages)
    # that need a plain region list — those pages now also see roster-only
    # regions, matching the Utilization Home behavior. See module docstring.
    if roster_df is not None and "Region" in roster_df.columns:
        regions = _union_clean(df["Region (EC)"], roster_df["Region"])
    else:
        regions = _union_clean(df["Region (EC)"])

    # markets: UNION of roster.Market + booking.Market (EC). Same rationale.
    if roster_df is not None and "Market" in roster_df.columns:
        markets = _union_clean(df["Market (EC)"], roster_df["Market"])
    else:
        markets = _union_clean(df["Market (EC)"])

    # departments: UNION of roster.Designation (the roster's canonical
    # department column per METRICS.md's "Departments" card — DAX is
    # DISTINCTCOUNT(HR MASTER[Designation])) + booking.Department.
    # Booking's `Department` is a coarser sub-function label (QA,
    # Engineering, ...); the roster's `Designation` is a finer job-title
    # ("SalesForce Core Developer"). Unioning them means the filter shows
    # every real value the user might filter on — a booking department
    # the roster doesn't cover would still appear (defensive), and a
    # roster job title with zero booked hours also appears (filters to
    # zero booking rows — matches "show all options" intent).
    if roster_df is not None and "Designation" in roster_df.columns:
        departments = _union_clean(df["Department"], roster_df["Designation"])
    else:
        departments = _union_clean(df["Department"])

    return {
        "weeks": sorted(w.strftime("%Y-%m-%d") for w in weeks),
        "week_hierarchy": week_hierarchy,
        "regions": regions,
        "markets": markets,
        "region_market_hierarchy": region_market_hierarchy,
        "departments": departments,
        # `entities`, `holdings`, `hours_types`, `employees` are booking-only —
        # no roster counterpart, no union. `employees` powers the Utilization
        # Search page's Employee filter (added 2026-07-24); same shape as the
        # other flat lists, blanks dropped, sorted for stable dropdown order.
        "entities": _union_clean(df["Team (EC)"]),
        "holdings": _union_clean(df["Holding"]),
        "hours_types": _union_clean(df["Booked Hours Type"]),
        # Guard the column access — some legacy test fixtures build a
        # booking-shaped frame without an `Employee` column, and every
        # other flat filter list here silently handles that shape via its
        # column presence too.
        "employees": (
            _union_clean(df["Employee"]) if "Employee" in df.columns else []
        ),
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
    employee: str | list[str] | None = None,
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

    Also excludes any row with no `Employee` (see `prepare_booking_df`'s
    docstring) from the returned rows. Such a row is already naturally
    excluded from SUM/nunique-based aggregations elsewhere in this module,
    but row-level listing (this function, and `records_to_dicts`
    downstream of it) needs an explicit exclusion or it surfaces as a
    ghost record with a null `employee` field.
    """
    # `df` is normally already `data_loader.get_booking_df_prepared()`
    # (no-Employee rows dropped, dates parsed) -- this check makes the
    # function idempotent/cheap to call again on an already-prepared frame
    # (e.g. from tests that pass the raw df), without redoing the parse on
    # every request in the common case.
    blank_mask = df["Employee"].isna()
    out = df[~blank_mask] if blank_mask.any() else df
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
    out = out[_matches_any(out["Employee"], _as_list(employee))]
    return out


@cache_on_df
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


def get_average_hours(df: pd.DataFrame) -> float:
    """
    `Average Hours` — mean of `Employee Booked Hours` across every row in
    the (typically filtered) slice. Declared as the `average_hours` card
    in `configs/booking_metrics.yaml` (`measure_type: mean`, introduced
    for the Utilization Results page's summary strip). PROVISIONAL — no
    Power BI counterpart in the exported model.
    Reads: `Employee Booked Hours`.
    Edge cases: empty frame -> 0.0 (matches the previous inline behaviour
    the Results page's summary strip already assumed).
    """
    return float(evaluate_booking_card(df, "average_hours"))


def get_records_summary(df: pd.DataFrame) -> dict:
    """
    Summary KPIs for a (typically filtered) slice of the booking sheet —
    Total/Client/Internal Hours, Total Projects, Average Hours. Powers the
    Results page's summary strip above the paginated table. All five
    values now route through `evaluate_booking_card` (see the declarations
    under `cards:` in `configs/booking_metrics.yaml`), so the Results
    strip and the Utilization Home strip cannot compute the same KPI
    differently — they read from the same declaration.
    Reads: `Booked Hours Type`, `Employee Booked Hours`, `Project Name`.
    """
    return {
        "total_hours": get_total_hours(df),
        "client_hours": get_client_hours(df),
        "internal_hours": get_internal_hours(df),
        "total_projects": get_total_projects(df),
        "average_hours": get_average_hours(df),
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
    out = df
    if not pd.api.types.is_datetime64_any_dtype(out["Monday of Week"]) or not pd.api.types.is_datetime64_any_dtype(
        out["Date"]
    ):
        out = out.copy()
        out["Monday of Week"] = pd.to_datetime(out["Monday of Week"])
        out["Date"] = pd.to_datetime(out["Date"])

    # Vectorized column-at-a-time projection instead of `.iterrows()` +
    # per-row dict building: `.iterrows()` boxes every row into a Series
    # (with dtype upcasting) before it can even be read, which measured
    # as the dominant cost of this whole endpoint (~25ms of the ~40ms
    # response time for a 500-row page) despite the underlying data being
    # tiny. `.where(notna, None)` + `.tolist()` per column, then
    # `zip(*columns)`, produces the same output an order of magnitude
    # faster while keeping identical None-handling semantics (NaN -> None
    # / omitted string, `Employee Booked Hours` NaN -> 0.0).
    week_start = out["Monday of Week"].dt.strftime("%Y-%m-%d").where(out["Monday of Week"].notna(), None).tolist()
    date = out["Date"].dt.strftime("%Y-%m-%d").where(out["Date"].notna(), None).tolist()
    employee = out["Employee"].where(out["Employee"].notna(), None).tolist()
    project = out["Project Name"].where(out["Project Name"].notna(), None).tolist()
    holding = out["Holding"].where(out["Holding"].notna(), None).tolist()
    hours_type = out["Booked Hours Type"].where(out["Booked Hours Type"].notna(), None).tolist()
    hours = out["Employee Booked Hours"].fillna(0.0).astype(float).tolist()
    region = out["Region (EC)"].where(out["Region (EC)"].notna(), None).tolist()
    department = out["Department"].where(out["Department"].notna(), None).tolist()
    team = out["Team (EC)"].where(out["Team (EC)"].notna(), None).tolist()

    return [
        {
            "week_start": ws,
            "date": d,
            "employee": e,
            "project": p,
            "holding": h,
            "hours_type": ht,
            "hours": hrs,
            "region": r,
            "department": dept,
            "team": t,
        }
        for ws, d, e, p, h, ht, hrs, r, dept, t in zip(
            week_start, date, employee, project, holding, hours_type, hours, region, department, team
        )
    ]


@cache_on_df
def get_employee_detail(df: pd.DataFrame, employee: str) -> dict | None:
    """
    Per-employee drill-through for the Employee Utilization page: Total/
    Client/Internal Hours, Total Projects (all four KPIs `filter_scope:
    whole_scope` — the endpoint hands the WHOLE employee's rows to
    `evaluate_booking_card`; page-local filters narrow only the charts,
    which live client-side today), Total Hours by Project
    (`employee_hours_by_project` chart, `sum_by`), Total Hours by Week
    Start + Hours Type (`employee_hours_by_week` chart, `sum_by_split`).

    Both charts are declared in `configs/booking_metrics.yaml` and
    computed by `evaluate_booking_chart`, so a shape change is a config
    edit (mirrors the roster's `evaluate_chart` contract).

    Reads: `Employee`, `Booked Hours Type`, `Employee Booked Hours`,
    `Project Name`, `Monday of Week`.
    Edge cases: returns None if `employee` has no rows at all (e.g. the
    unresolved `Amit Singh`/`Ankit Singh` name-variant case per
    data-model SKILL.md — callers should 404, not crash, on None).
    """
    rows = df[df["Employee"] == employee]
    if rows.empty:
        return None

    # Hours by Project — declared `sum_by`. Sort desc so the frontend can
    # render straight from the array (mirrors the old inline behaviour).
    by_project = evaluate_booking_chart(rows, "employee_hours_by_project")
    hours_by_project = [
        {"project": project, "total_hours": float(hours)}
        for project, hours in sorted(by_project.items(), key=lambda kv: kv[1], reverse=True)
    ]

    # Hours by Week — declared `sum_by_split` (group=Monday of Week,
    # split=Booked Hours Type). The dispatcher returns
    # {"group": "<week>", "Client Hours": v, "Internal Hours": v} rows;
    # this reshapes to the response model's {week_start, client_hours,
    # internal_hours} contract and normalises Timestamps to ISO date.
    weekly = rows.copy()
    weekly["Monday of Week"] = pd.to_datetime(weekly["Monday of Week"])
    week_rows = evaluate_booking_chart(weekly, "employee_hours_by_week")
    hours_by_week = [
        {
            "week_start": pd.Timestamp(row["group"]).strftime("%Y-%m-%d"),
            "client_hours": float(row.get(CLIENT_HOURS_LABEL, 0.0)),
            "internal_hours": float(row.get(INTERNAL_HOURS_LABEL, 0.0)),
        }
        for row in week_rows
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


@cache_on_df
def get_project_detail(df: pd.DataFrame, holding: str) -> dict | None:
    """
    Per-project/holding drill-through for the Project Utilization page:
    Total/Client/Internal Hours KPIs (`filter_scope: whole_scope` — see
    `get_employee_detail`), Total Hours by Employee + Hours Type
    (`project_hours_by_employee`, `sum_by_split`), Total Hours by Week
    Start + Hours Type (`project_hours_by_week`, `sum_by_split`), plus a
    detail-table projection (Employee, Project, Region, Department) that
    stays as a code helper per METRICS.md Page 10's "the detail table is
    a projection, not an aggregation" note.

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

    # Hours by Employee — declared `sum_by_split` (group=Employee,
    # split=Booked Hours Type). The dispatcher returns
    # {"group": "<name>", "Client Hours": v, "Internal Hours": v} rows;
    # this reshapes to the response model's {employee, client_hours,
    # internal_hours} contract.
    emp_rows = evaluate_booking_chart(by_employee, "project_hours_by_employee")
    hours_by_employee = [
        {
            "employee": row["group"],
            "client_hours": float(row.get(CLIENT_HOURS_LABEL, 0.0)),
            "internal_hours": float(row.get(INTERNAL_HOURS_LABEL, 0.0)),
        }
        for row in emp_rows
    ]

    # Hours by Week — same shape as Employee page's week chart.
    week_rows = evaluate_booking_chart(by_employee, "project_hours_by_week")
    hours_by_week = [
        {
            "week_start": pd.Timestamp(row["group"]).strftime("%Y-%m-%d"),
            "client_hours": float(row.get(CLIENT_HOURS_LABEL, 0.0)),
            "internal_hours": float(row.get(INTERNAL_HOURS_LABEL, 0.0)),
        }
        for row in week_rows
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


@cache_on_df
def get_hours_split(df: pd.DataFrame) -> dict[str, float]:
    """
    Hours grouped by `Booked Hours Type`, from the chart declared in
    `configs/booking_metrics.yaml`.

    Declared rather than hardcoded so this donut works the same way as
    every roster chart. `sum_by` exists because hours are a quantity to be
    summed, not rows to be counted — and because summing straight from the
    data means a category the config has never seen still appears, instead
    of being silently dropped from the donut.
    """
    return evaluate_booking_chart(df, "internal_vs_client_hours")
