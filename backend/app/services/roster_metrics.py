"""
Aggregation functions over the employee roster (`HR MASTER` in the real
Power BI model), sourced from `backend/data/DEPT_-_Master_Data_Sheet1_.xlsx`.

Design notes (per api-conventions SKILL.md "Excel/DB swap boundary"):
- Every public function takes either a DataFrame (`df`) or a `path`
  defaulting to the real Excel file, and returns a plain dict/scalar.
  When the backing store moves to a DB, only `load_roster()` needs to
  change — callers and signatures stay stable.
- Source column names are kept EXACTLY as they appear in the Excel file
  (including the `Seniorirty Level` typo) all the way through this
  module. Renaming to clean names (e.g. `seniority_level`) is deferred
  to the output/response layer (not built in this pass).

Data-quality handling (per data-model SKILL.md):
- `Total Experience` is validated against
  `Hexaware Experience (Years) + Before Hexaware Experience` on load.
  Mismatching rows are logged as a named warning and INCLUDED as-is
  (never silently recomputed/overwritten) via `get_data_quality_warnings()`.
- Unexpected `Status` values (anything other than "Active"/"Inactive")
  are logged as a warning, not dropped or coerced.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from app.services import metric_config
from app.services.calendar import build_available_months
from app.services.cache_utils import cache_on_df

logger = logging.getLogger(__name__)

DEFAULT_ROSTER_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "DEPT - Master Data(Sheet1).xlsx"
)

EXPERIENCE_TOLERANCE = 0.01  # years; float rounding tolerance

# Status literals and the seniority keyword map now come from
# `configs/roster_metrics.yaml`, so changing what counts as present, or
# adding a seniority keyword, is a config edit rather than a code change.
# Every surface that reports Strategic Pool resolves through
# `get_strategic_pool`, so the Home and HR Home donuts can never disagree
# again (see metric_invariants.py, which asserts it).
STRATEGIC_POOL_STATUS = metric_config.status_value("strategic_pool")


def _chart_scope(df: pd.DataFrame, spec: dict) -> pd.DataFrame:
    """
    Which population a chart describes, per its declared `scope`.

    Declared explicitly because it genuinely differs between pages: HR
    Home describes the whole roster (its headline is Total Employees, and
    its Status Split has to show Inactive at all), Home describes the
    current workforce (its headline is Closing Headcount).
    """
    scope = spec.get("scope", "all")
    if scope == "present":
        return df[metric_config.is_present(df)]
    if scope == "exited":
        # People who actually left — a recorded leaving date. Used by the
        # Voluntary vs Involuntary donut so it describes leavers only.
        return df[df[metric_config.column("leaving_date")].notna()]
    if scope != "all":
        raise ValueError(f"Chart declares unknown scope={scope!r}")
    return df


def evaluate_chart(df: pd.DataFrame, chart_name: str) -> dict[str, int]:
    """
    Compute a breakdown chart from its declaration in
    `configs/roster_metrics.yaml`, as `{label: distinct employees}`.

    Blank values are counted under the chart's `blank_label` rather than
    dropped. Dropping them is how a bar chart silently ends up totalling
    less than the headline card above it, with nothing on screen to
    explain the gap — the labels ("Region TBD", "Entity TBD") match the
    convention already used in the data, so a blank folds in with the
    existing TBD rows instead of creating a second bucket.

    Supported `type`s: `count_by` (group by a column), `numeric_bands`
    (bucket a number by declared thresholds) and `keyword_bands` (bucket
    text by the configured keyword rules).
    """
    spec = metric_config.chart(chart_name)
    if spec["type"] == "monthly_series":
        return _evaluate_monthly_series(df, spec)

    scope = _chart_scope(df, spec)
    keys = chart_labels(scope, spec)

    counts = {
        str(label): get_total_employees(group)
        for label, group in scope.groupby(keys, dropna=True)
    }

    # Declared buckets/bands always appear, even at zero, so a slice never
    # silently disappears from a donut; declaration order is preserved.
    declared = (
        [b["label"] for b in spec["bands"]]
        if spec["type"] == "numeric_bands"
        else spec.get("buckets", [])
    )
    ordered = {label: counts.pop(label, 0) for label in declared}
    ordered.update(counts)  # anything unexpected still shows, after the declared ones
    return ordered


def _evaluate_monthly_series(df: pd.DataFrame, spec: dict) -> list[dict]:
    """
    Walk the dataset's month range and evaluate each declared series per
    month, returning one row per month.

    A series is either a `measure` (a named metric evaluated for that
    month, e.g. closing_headcount) or a `date_role` (count the employees
    whose date in that column falls inside the month). Declaring these in
    the same `charts:` block as the group-by charts means every chart on
    the dashboard is defined in one place — a time-series chart used to be
    bespoke Python that only looked config-driven because it happened to
    read its column names from config.
    """
    available = build_available_months(df)
    measures = {"closing_headcount": get_closing_headcount}

    rows: list[dict] = []
    for month_start in available.month_starts:
        month_end = month_start + pd.offsets.MonthEnd(0)
        row: dict = {"month": month_start.strftime("%b %Y")}
        for series in spec["series"]:
            if "measure" in series:
                row[series["key"]] = measures[series["measure"]](
                    df, period_month=month_start
                )
                continue
            dates = pd.to_datetime(
                df[metric_config.column(series["date_role"])],
                format=DATE_FORMAT,
                errors="coerce",
            )
            in_month = dates.notna() & (dates >= month_start) & (dates <= month_end)
            row[series["key"]] = get_total_employees(df[in_month])
        rows.append(row)
    return rows


def chart_labels(df: pd.DataFrame, spec: dict) -> pd.Series:
    """
    The bucket label each row falls into for a chart declaration.

    Shared by `evaluate_chart` (to count them) and `apply_filters` (to
    filter by one). A page filtering on "Experience Band = 5-8 Years" must
    use the same thresholds the chart uses — deriving them separately, as
    the frontend used to, is how a filter and the chart it filters end up
    disagreeing.
    """
    column = metric_config.column(spec["column_role"])
    blank_label = spec.get("blank_label")
    kind = spec["type"]

    if kind == "count_by":
        keys = df[column]
        if blank_label is not None:
            keys = keys.where(
                keys.notna() & (keys.astype(str).str.strip() != ""), blank_label
            )
        return keys
    if kind == "numeric_bands":
        values = pd.to_numeric(df[column], errors="coerce")
        return values.apply(lambda v: _numeric_band(v, spec["bands"], blank_label))
    if kind == "keyword_bands":
        return df[column].apply(_seniority_category)
    raise ValueError(f"Chart declares unsupported type={kind!r}")


def _numeric_band(value: float, bands: list[dict], blank_label: str | None) -> str:
    """First band whose `below` the value falls under; last band catches the rest."""
    if pd.isna(value):
        return blank_label or "Unknown"
    for band in bands:
        if "below" not in band:
            return band["label"]
        if value < band["below"]:
            return band["label"]
    return bands[-1]["label"]


def evaluate_card(df: pd.DataFrame, card_name: str) -> int:
    """
    Compute a KPI card straight from its declaration in
    `configs/roster_metrics.yaml`.

    The `cards:` block is the definition of record — what the card
    counts, which column role it counts it over, and whether a status
    filter applies. Routing the actual computation through it is what
    makes the YAML authoritative rather than merely descriptive: edit the
    declaration and the number on screen changes. (Before this, the block
    was documentation only — pointing `projects` at a different column
    changed nothing, which is worse than having no declaration at all,
    because it reads as if it were in charge.)

    Supported today: `counts: distinct` over a column role, an optional
    `status_filter`, and `normalize_case` for headings whose values vary
    only by capitalisation.
    """
    spec = metric_config.card(card_name)

    scope = df
    status_filter = spec.get("status_filter", "none")
    if status_filter and status_filter != "none":
        scope = scope[
            scope[metric_config.status_column()]
            == metric_config.status_value(status_filter)
        ]

    values = scope[metric_config.column(spec["column_role"])]
    if spec.get("normalize_case"):
        # e.g. "SalesForce Core Developer" and "Salesforce Core Developer"
        # are one job title, not two.
        values = values.apply(
            lambda v: _normalize_designation_label(v) if pd.notna(v) else v
        )

    counts = spec.get("counts", "distinct")
    if counts != "distinct":
        raise ValueError(
            f"Card {card_name!r} declares unsupported counts={counts!r}; "
            "only 'distinct' is implemented."
        )
    return int(values.nunique(dropna=True))

DATE_FORMAT = "%d-%b-%y"  # source format, e.g. "24-Nov-25"


def load_roster(path: str | Path = DEFAULT_ROSTER_PATH) -> pd.DataFrame:
    """
    Read the roster Excel file, keeping source column names exactly as-is.

    Returns the raw DataFrame (52 rows in the confirmed source file).
    Row count is logged so silent drops during any later processing are
    detectable by comparing against this log line.
    """
    df = pd.read_excel(path)
    logger.info("load_roster: read %d rows from %s", len(df), path)
    return df


@cache_on_df
def get_data_quality_warnings(df: pd.DataFrame) -> list[dict]:
    """
    Surface (not fix) known data-quality issues:
      1. `Total Experience` != `Hexaware Experience (Years)` +
         `Before Hexaware Experience` (beyond float tolerance).
      2. `Status` values outside the expected {"Active", "Inactive"} set.

    Returns a list of warning dicts: {"type": ..., "row_id": ..., "detail": ...}
    Never mutates or drops rows — purely informational.
    """
    warnings: list[dict] = []

    computed_total = df["Hexaware Experience (Years)"] + df["Before Hexaware Experience"]
    mismatch_mask = (computed_total - df["Total Experience"]).abs() > EXPERIENCE_TOLERANCE
    for _, row in df[mismatch_mask].iterrows():
        warnings.append(
            {
                "type": "total_experience_mismatch",
                "row_id": row.get("NEW_EMP_ID"),
                "detail": (
                    f"Total Experience={row['Total Experience']} but "
                    f"Hexaware+Before={row['Hexaware Experience (Years)']}+"
                    f"{row['Before Hexaware Experience']}="
                    f"{row['Hexaware Experience (Years)'] + row['Before Hexaware Experience']}"
                ),
            }
        )

    # "Strategic Pool" added 2026-07-17 at the business owner's explicit
    # direction: the 2 employees with a blank/TBD `DOJ (DEPT)` (already
    # confirmed via `get_strategic_pool`'s ISBLANK(DOJ (DEPT)) filter —
    # NEW_EMP_ID 2000194634, 2000195658) now also carry this Status value
    # directly, so `Active Employees` (Status == "Active") correctly
    # excludes them instead of double-counting them as both Active and
    # Strategic Pool. See data-model SKILL.md for the full writeup.
    expected_statuses = {"Active", "Inactive", "Strategic Pool"}
    unexpected_mask = ~df["Status"].isin(expected_statuses)
    for _, row in df[unexpected_mask].iterrows():
        warnings.append(
            {
                "type": "unexpected_status_value",
                "row_id": row.get("NEW_EMP_ID"),
                "detail": f"Status={row.get('Status')!r}",
            }
        )

    # 3. `DOJ (DEPT)` values that don't parse as a date at all (e.g. the
    #    literal string "TBD") — confirmed present in the real file for
    #    2 rows (NEW_EMP_ID 2000194634, 2000195658). These rows cannot be
    #    placed on either side of any date-based headcount cutoff
    #    (Closing/Opening Headcount, Joiners), so they are logged here
    #    AND excluded from date-based comparisons (never silently treated
    #    as "joined" or "not joined" by guessing a date).
    if "DOJ (DEPT)" in df.columns:
        joining = df[metric_config.column("joining_date")]
        parsed = pd.to_datetime(joining, format=DATE_FORMAT, errors="coerce")
        unparseable_mask = joining.notna() & parsed.isna()
        for _, row in df[unparseable_mask].iterrows():
            warnings.append(
                {
                    "type": "doj_dept_unparseable",
                    "row_id": row.get("NEW_EMP_ID"),
                    "detail": f"DOJ (DEPT)={row.get('DOJ (DEPT)')!r} is not a valid date",
                }
            )

    # 4. `Seniorirty Level` values that contain "senior"/"lead" only in a
    #    non-standard casing (e.g. "Premium lead", "Standard senior").
    #    `get_senior_lead_employees` uses CONTAINSSTRING's case-sensitive
    #    default and so does NOT count these rows -- flagged here so the
    #    casing inconsistency is visible rather than silently absorbed
    #    into (or excluded from) that metric.
    if "Seniorirty Level" in df.columns:
        seniority = df["Seniorirty Level"].fillna("").astype(str)
        case_sensitive_mask = seniority.str.contains(
            "Senior", case=True, regex=False
        ) | seniority.str.contains("Lead", case=True, regex=False)
        case_insensitive_mask = seniority.str.contains(
            "senior", case=False, regex=False
        ) | seniority.str.contains("lead", case=False, regex=False)
        casing_only_mask = case_insensitive_mask & ~case_sensitive_mask
        for _, row in df[casing_only_mask].iterrows():
            warnings.append(
                {
                    "type": "seniority_level_casing_mismatch",
                    "row_id": row.get("NEW_EMP_ID"),
                    "detail": (
                        f"Seniorirty Level={row['Seniorirty Level']!r} contains "
                        "'senior'/'lead' only in non-standard casing -- excluded "
                        "from Senior - Lead Employees (case-sensitive CONTAINSSTRING)"
                    ),
                }
            )

    # 5. `Designation` values that are casing-duplicates of each other
    #    (confirmed in the real file: "SalesForce Core Developer" vs
    #    "Salesforce Core Developer"). `get_departments` normalizes these
    #    to title-case before counting distinct values (see
    #    `_normalize_designation_label`) -- flagged here so the
    #    underlying source inconsistency remains visible rather than
    #    silently absorbed by the normalization.
    if "Designation" in df.columns:
        designation = df[metric_config.column("designation")].dropna().astype(str)
        normalized_designation = designation.apply(_normalize_designation_label)
        dup_normalized = normalized_designation[
            normalized_designation.duplicated(keep=False)
        ].unique()
        # Only flag normalized groups that actually contain more than one
        # distinct RAW casing variant (i.e. a genuine casing mismatch, not
        # just multiple rows sharing the same already-consistent spelling).
        for norm_label in dup_normalized:
            raw_variants = designation[normalized_designation == norm_label].unique()
            if len(raw_variants) > 1:
                mask = df[metric_config.column("designation")].isin(raw_variants)
                for _, row in df[mask].iterrows():
                    warnings.append(
                        {
                            "type": "designation_casing_mismatch",
                            "row_id": row.get("NEW_EMP_ID"),
                            "detail": (
                                f"Designation={row['Designation']!r} is a casing "
                                f"variant of other rows normalizing to "
                                f"{norm_label!r} -- collapsed together by "
                                "get_departments() via _normalize_designation_label"
                            ),
                        }
                    )

    if warnings:
        logger.warning("get_data_quality_warnings: %d warning(s) found", len(warnings))
    return warnings


# --------------------------------------------------------------------------
# Date-period helpers (for Closing/Opening Headcount, Joiners, Exits)
# --------------------------------------------------------------------------


def _parse_dept_dates(df: pd.DataFrame) -> pd.Series:
    """
    Parse `DOJ (DEPT)` as dates. Unparseable values (e.g. literal "TBD",
    confirmed present for 2 rows in the real file) become NaT rather than
    raising — those rows are surfaced separately via
    `get_data_quality_warnings` (type "doj_dept_unparseable").

    CORRECTED (2026-07-16): the resulting NaT is DAX's BLANK(), not "a
    comparison that always fails". In real DAX, BLANK() in a numeric/date
    comparison context behaves like the value 0 (epoch-zero,
    1899-12-30) -- so `BLANK() <= EndDate` is TRUE and `BLANK() >=
    StartDate` is FALSE (since any real StartDate is after epoch-zero),
    and `ISBLANK(BLANK())` is TRUE. pandas' NaT comparisons always
    evaluate False regardless of operator direction, which is NOT
    equivalent -- callers of this function must NOT rely on NaT's default
    comparison behavior and must instead explicitly encode DAX's
    blank-as-zero semantics for each comparison direction (see
    `get_closing_headcount`, `get_opening_headcount`, `get_joiners`, and
    `get_strategic_pool` for the explicit per-direction handling this
    requires). This was previously (incorrectly) documented as
    "DAX-faithful" -- it was not; see data-model SKILL.md "Known open
    data gap" (now resolved) for the full writeup.
    """
    return pd.to_datetime(
        df[metric_config.column("joining_date")], format=DATE_FORMAT, errors="coerce"
    )


def _parse_lwd_dates(df: pd.DataFrame) -> pd.Series:
    """Parse `LWD` as dates; blank cells (the expected case for Active
    employees) become NaT."""
    return pd.to_datetime(
        df[metric_config.column("leaving_date")], format=DATE_FORMAT, errors="coerce"
    )


def _resolve_period(
    df: pd.DataFrame, period_month: pd.Timestamp | str | None = None
) -> tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp]:
    """
    Resolve (StartDate, EndDate, PreviousDate) for the date-based
    headcount measures, mirroring the real DAX's dependence on
    `'Available Months'[Month Start]` (StartDate/EndDate) and
    `'Calendar'[Date]` (PreviousDate).

    DEFAULT (no `period_month` passed) — per explicit user decision, this
    resolves to the FULL DATE RANGE of the dataset, i.e. `MIN`/`MAX` of
    `'Available Months'[Month Start]` with no month filter applied:
      - Uses `calendar.build_available_months(df)` to derive the full
        `Available Months` range from the roster's `DOJ (DEPT)` / `LWD` /
        `Today` columns (see that module's docstring for the exact
        boundary logic).
      - StartDate = MIN('Available Months'[Month Start]) = first day of
        the earliest month in the dataset.
      - EndDate = EOMONTH(MAX('Available Months'[Month Start]), 0) = last
        day of the latest month in the dataset.
      - PreviousDate = MIN('Calendar'[Date]) - 1, i.e. the day *before*
        the single earliest actual date anywhere in the dataset (NOT
        rounded to a month start — see calendar.py's `earliest_date`).
        This is a deliberate interpretation choice: the real DAX's
        `Opening Headcount` measure is written for a single selected
        month, where "PreviousDate" means "the day before this month
        began." There's no single natural analogue for "the day before
        all of history" — the only date that means the same thing
        ("nothing has happened yet") for a full-range selection is the
        day immediately before the earliest event in the data. In
        practice this makes full-range Opening Headcount return 0 for
        any dataset where the earliest month's start date and the
        earliest actual DOJ date coincide (which they always will here,
        since `earliest_date` literally *is* `MIN(DOJ (DEPT))`) — i.e.
        "headcount before the first employee joined" = 0. This is
        reported honestly, not forced to match a nonzero reference
        number.

    EXPLICIT `period_month` (any date within the desired month, e.g.
    `pd.Timestamp("2026-06-01")`) — reproduces the OLD single-month
    behavior for that month, kept for future filter-UI use (Phase 5):
      - StartDate = first day of that month
      - EndDate = last day of that month
      - PreviousDate = StartDate - 1 day
    """
    if period_month is None:
        available_months = build_available_months(df)
        if not available_months.month_starts:
            # A filter can legitimately select zero rows (or rows with no
            # joining date). Return an empty window so every date measure
            # reports zero, rather than the page erroring out.
            empty = pd.Timestamp.min + pd.Timedelta(days=1)
            return empty, empty, empty
        start = available_months.min_month_start
        end = available_months.max_month_end
        previous = available_months.earliest_date - pd.Timedelta(days=1)
        return start, end, previous

    month_ts = pd.to_datetime(period_month, format=DATE_FORMAT, errors="coerce")
    if pd.isna(month_ts):
        month_ts = pd.to_datetime(period_month)
    start = month_ts.replace(day=1)
    end = start + pd.offsets.MonthEnd(0)
    previous = start - pd.Timedelta(days=1)
    return start, end, previous


# --------------------------------------------------------------------------
# Headcount / status
# --------------------------------------------------------------------------


@cache_on_df
def get_active_employees(df: pd.DataFrame) -> int:
    """
    `Active Employees` = CALCULATE([Total Employees], Status = "Active")
    i.e. DISTINCTCOUNT(NEW_EMP_ID) restricted to Status == "Active".
    ALREADY CORRECT in effect for this dataset (no duplicate NEW_EMP_ID
    rows), but tightened to `nunique` on `NEW_EMP_ID` to match the real
    DAX's DISTINCTCOUNT semantics exactly rather than a raw row-count sum.
    Reads: `Status`, `NEW_EMP_ID`.
    Edge cases: blank/NaN Status rows are excluded (not counted as active).
    """
    return evaluate_card(df, "active_employees")


@cache_on_df
def get_inactive_employees(df: pd.DataFrame) -> int:
    """
    `Inactive Employees` = CALCULATE([Total Employees], Status = "Inactive").
    Reads: `Status`, `NEW_EMP_ID`.
    """
    return get_total_employees(df[df["Status"] == "Inactive"])


@cache_on_df
def get_total_employees(df: pd.DataFrame) -> int:
    """
    `Total Employees` = DISTINCTCOUNT('HR MASTER'[NEW_EMP_ID]).

    FIXED: previously this returned `len(df)` (raw row count, effectively
    unfiltered but not distinct-safe), which happened to equal the real
    DAX's result only because the roster has one row per employee with no
    duplicate `NEW_EMP_ID`s. The real DAX is a DISTINCTCOUNT over
    `NEW_EMP_ID` and is explicitly NOT filtered by `Status` (confirmed in
    data-model SKILL.md "Corrections" section) — `Active Employees` /
    `Inactive Employees` are the ones that add the `Status` filter via
    `CALCULATE([Total Employees], ...)`.
    Reads: `NEW_EMP_ID`.
    """
    return evaluate_card(df, "total_employees")


@cache_on_df
def get_active_pct(df: pd.DataFrame) -> float:
    """
    `Active %` — Active Employees / Total Employees * 100.
    Reads: `Status`.
    Edge cases: returns 0.0 if the roster is empty (avoids div-by-zero).
    """
    total = get_total_employees(df)
    if total == 0:
        return 0.0
    return get_active_employees(df) / total * 100


# --------------------------------------------------------------------------
# Attrition
# --------------------------------------------------------------------------


@cache_on_df
def get_closing_headcount(
    df: pd.DataFrame, period_month: pd.Timestamp | str | None = None
) -> int:
    """
    `Closing Headcount` =
        VAR EndDate = EOMONTH(MAX('Available Months'[Month Start]), 0)
        RETURN CALCULATE([Total Employees], FILTER('HR Master',
            'HR Master'[DOJ (DEPT)] <= EndDate &&
            (ISBLANK('HR Master'[LWD]) || 'HR Master'[LWD] > EndDate)))

    Date-based, independent of `Status` — an employee with
    Status = "Inactive" can still be counted here if their `LWD` is after
    EndDate (or blank), and vice versa; do not conflate with
    `Active Employees`.

    DEFAULT PERIOD (no `period_month` passed): per explicit user
    decision, resolves to the FULL DATE RANGE of the dataset — EndDate
    is the end of the *latest* month in `calendar.build_available_months(df)`,
    not just the month of the `Today` snapshot column. Pass an explicit
    `period_month` (any date within the desired month) to scope to a
    single month instead — see `_resolve_period` for full details.

    Edge cases: rows whose `DOJ (DEPT)` fails to parse (e.g. literal
    "TBD", see `get_data_quality_warnings`) are treated as having joined
    (see the blank-DOJ note below).

    REDEFINED (2026-07-22, business owner): Closing Headcount is now
    "everyone who had joined by the end of the period AND is still part of
    the workforce", where "still here" means `Status` is one of
    `counts_as_present` in configs/roster_metrics.yaml (Active + Strategic
    Pool). Inactive employees are never counted, regardless of LWD.

    This replaces the old LWD-based exit test, which produced a visible
    contradiction on the Home page: 9 employees were marked Inactive but
    had no LWD, so the date logic still counted them as present and the
    KPI read 47 while the Active+Strategic donut on the same page read 38.
    Keying off Status instead makes the whole page agree by construction,
    and makes the trend behave the way the business describes it: purely
    cumulative by joining date (May 34 + 2 June joiners = June 36).

    Reads: `DOJ (DEPT)`, `Status`, `Today`, `NEW_EMP_ID`.
    """
    _, end, _ = _resolve_period(df, period_month)
    doj = _parse_dept_dates(df)
    # DAX BLANK() semantics fix (2026-07-16): a blank/unparseable DOJ (DEPT)
    # (e.g. the literal string "TBD", parsed to NaT) behaves in real DAX
    # like the value 0 (epoch-zero, 1899-12-30) inside a numeric/date
    # comparison -- so `DOJ (DEPT) <= EndDate` evaluates TRUE for a blank,
    # NOT False. pandas' NaT comparisons always evaluate False regardless
    # of operator direction, which silently diverges from DAX here. Made
    # explicit: `doj.isna() | (doj <= end)` treats blank as satisfying
    # `<=` intentionally, rather than relying on (wrong) NaT default
    # behavior. See data-model SKILL.md "Known open data gap" (now
    # resolved) for the full root-cause writeup. Kept for the same reason
    # here: an employee with an unrecorded joining date is still part of
    # the workforce, so a blank DOJ must not drop them from headcount.
    joined_by_end = doj.isna() | (doj <= end)
    # "Still here" is Status-driven (config: counts_as_present), NOT
    # LWD-driven — see the docstring for why.
    mask = joined_by_end & metric_config.is_present(df)
    return get_total_employees(df[mask])


@cache_on_df
def get_opening_headcount(
    df: pd.DataFrame, period_month: pd.Timestamp | str | None = None
) -> int:
    """
    `Opening Headcount` =
        VAR StartDate = MIN('Calendar'[Date])
        VAR PreviousDate = StartDate - 1
        RETURN CALCULATE([Total Employees], FILTER('HR Master',
            'HR MASTER'[DOJ (DEPT)] <= PreviousDate &&
            (ISBLANK('HR Master'[LWD]) || 'HR Master'[LWD] > PreviousDate)))

    Same date logic as `get_closing_headcount` but against
    PreviousDate = (period StartDate - 1 day).

    DEFAULT PERIOD (no `period_month` passed): full date range of the
    dataset. PreviousDate = the day before `MIN('Calendar'[Date])`
    (the single earliest actual date anywhere in the roster, NOT rounded
    to a month start) — see `_resolve_period` and `calendar.py` for why
    this is the chosen interpretation, and note it makes full-range
    Opening Headcount 0 by construction (no one is employed before the
    earliest recorded join date). Pass an explicit `period_month` to
    scope to a single month instead.

    Reads: `DOJ (DEPT)`, `LWD`, `Today`, `NEW_EMP_ID`.
    """
    _, _, previous = _resolve_period(df, period_month)
    doj = _parse_dept_dates(df)
    lwd = _parse_lwd_dates(df)
    # DAX BLANK() semantics fix (2026-07-16): same reasoning as
    # `get_closing_headcount` -- blank DOJ (DEPT) behaves like epoch-zero
    # in DAX, so it always satisfies `<= PreviousDate`. Made explicit
    # rather than relying on NaT's (wrong) default-False comparison.
    mask = (doj.isna() | (doj <= previous)) & (lwd.isna() | (lwd > previous))
    return get_total_employees(df[mask])


@cache_on_df
def get_joiners(df: pd.DataFrame, period_month: pd.Timestamp | str | None = None) -> int:
    """
    `Joiners` =
        VAR StartDate = MIN('Available Months'[Month Start])
        VAR EndDate = EOMONTH(MAX('Available Months'[Month Start]), 0)
        RETURN CALCULATE([Total Employees], FILTER('HR MASTER',
            'HR MASTER'[DOJ (DEPT)] >= StartDate &&
            'HR MASTER'[DOJ (DEPT)] <= EndDate))

    Uses `DOJ (DEPT)` (an internal-transfer-aware measure, consistent
    with Closing/Opening Headcount) — not `DOJ (Hexaware)` as an earlier
    provisional definition had guessed.

    DEFAULT PERIOD (no `period_month` passed): full date range of the
    dataset — StartDate/EndDate span every month present, so this counts
    every employee whose `DOJ (DEPT)` falls anywhere in the dataset's
    history. Pass an explicit `period_month` to scope to a single month.

    Reads: `DOJ (DEPT)`, `Today`, `NEW_EMP_ID`.
    """
    start, end, _ = _resolve_period(df, period_month)
    doj = _parse_dept_dates(df)
    # DAX BLANK() semantics note (2026-07-16): a blank DOJ (DEPT) behaves
    # like epoch-zero (1899-12-30) in DAX comparisons, which is always
    # LESS than any real StartDate -- so `DOJ (DEPT) >= StartDate` is
    # always FALSE for a blank, i.e. blank correctly does NOT count as a
    # joiner. This happens to already match pandas' NaT-always-False
    # comparison behavior for this specific operator direction, but that
    # match is coincidental to the direction, not a general guarantee
    # (see get_closing_headcount/get_opening_headcount, where the
    # opposite direction required an explicit fix). `doj.notna()` is
    # added here anyway to make the intent explicit/intentional for a
    # future reader, rather than leaving it as an accidental side effect
    # of NaT semantics.
    mask = doj.notna() & (doj >= start) & (doj <= end)
    return get_total_employees(df[mask])


@cache_on_df
def get_exits(df: pd.DataFrame) -> int:
    """
    `Exits` — how many people have left. Confirmed 2026-07-22 to be the
    same thing as Inactive: same people, same number.

    Was previously counted from `LWD` dates, which returned 5 while
    Inactive returned 14 — the same set of employees described two ways,
    because 9 of them are marked Inactive with no last working day
    recorded. There is one definition now, and it is the Status column.

    Deliberately has NO period argument: a status is a current fact, not
    a dated event. The month-by-month trends need a date to place an exit
    in time, so they use `get_dated_exits` instead and currently cover 5
    of these 14 — a known, accepted difference (this answers "how many
    have left", the trend answers "when did the ones we have dates for
    leave").
    Reads: `Status`, `NEW_EMP_ID`.
    """
    return evaluate_card(df, "exits")


@cache_on_df
def get_dated_exits(df: pd.DataFrame, period_month: pd.Timestamp | str | None = None) -> int:
    """
    Exits placed in TIME, from `LWD` dates — the series behind the
    month-by-month trends. Only counts employees whose last working day
    is recorded and falls in the period, so it is a subset of `get_exits`
    (5 of 14 today). See `get_exits` for why the two differ.

    Original DAX this implements:

    `Exits` =
        VAR StartDate = MIN('Available Months'[Month Start])
        VAR EndDate = EOMONTH(MAX('Available Months'[Month Start]), 0)
        RETURN CALCULATE([Total Employees], FILTER('HR MASTER',
            NOT ISBLANK('HR MASTER'[LWD]) &&
            'HR MASTER'[LWD] >= StartDate && 'HR MASTER'[LWD] <= EndDate))

    This is NOT the same as `Inactive Employees` — an employee could be
    Status = "Inactive" with an LWD outside the selected period (or, in
    principle, vice versa); this counts strictly by the `LWD` date
    falling inside [StartDate, EndDate].

    DEFAULT PERIOD (no `period_month` passed): full date range of the
    dataset — counts every employee whose `LWD` falls anywhere in the
    dataset's history. Pass an explicit `period_month` to scope to a
    single month.

    Reads: `LWD`, `Today`, `NEW_EMP_ID`.
    """
    start, end, _ = _resolve_period(df, period_month)
    lwd = _parse_lwd_dates(df)
    mask = lwd.notna() & (lwd >= start) & (lwd <= end)
    return get_total_employees(df[mask])


@cache_on_df
def get_attrition_pct(
    df: pd.DataFrame, period_month: pd.Timestamp | str | None = None
) -> float:
    """
    `Attrition %` = DIVIDE([Exits], [Closing Headcount] + [Exits]).

    Denominator is `Closing Headcount + Exits` (date-based measures, see
    `get_closing_headcount` / `get_exits`) — NOT the Status-based
    Active/Inactive counts an earlier provisional definition had guessed.

    DEFAULT PERIOD (no `period_month` passed): full date range of the
    dataset, via `get_closing_headcount`/`get_exits`'s own defaults. Pass
    an explicit `period_month` to scope to a single month.

    Reads: (via get_closing_headcount/get_exits) `DOJ (DEPT)`, `LWD`,
    `Today`, `NEW_EMP_ID`.
    Edge cases: returns 0.0 if Closing Headcount + Exits == 0.
    """
    exits = get_exits(df)
    closing = get_closing_headcount(df, period_month)
    denom = closing + exits
    if denom == 0:
        return 0.0
    return exits / denom * 100


@cache_on_df
def get_voluntary_leavers(df: pd.DataFrame) -> int:
    """
    `Voluntary Leavers` — count of Inactive rows where
    `Reason for Leaving` == "Voluntary".
    Reads: `Status`, `Reason for Leaving`.
    Edge cases: only Inactive rows are considered; `Reason for Leaving`
    is expected blank for Active rows per data-model and is not counted.
    """
    inactive = df[df["Status"] == "Inactive"]
    reason = inactive[metric_config.column("leaving_reason")]
    return int((reason == metric_config.leaving_reason("voluntary")).sum())


@cache_on_df
def get_involuntary_leavers(df: pd.DataFrame) -> int:
    """
    `InVoluntary Leavers` — count of Inactive rows where
    `Reason for Leaving` == "Involuntary".
    Reads: `Status`, `Reason for Leaving`.
    """
    inactive = df[df["Status"] == "Inactive"]
    reason = inactive[metric_config.column("leaving_reason")]
    return int((reason == metric_config.leaving_reason("involuntary")).sum())


# --------------------------------------------------------------------------
# Org splits
# --------------------------------------------------------------------------


@cache_on_df
def get_gcc_employees(df: pd.DataFrame) -> int:
    """
    `GCC Employees` = CALCULATE([Total Employees], Type = "GCC").
    ALREADY CORRECT in effect (no duplicate NEW_EMP_ID rows in this
    dataset), tightened to route through `get_total_employees`
    (DISTINCTCOUNT semantics) rather than a raw row-count sum, matching
    the real DAX's `CALCULATE([Total Employees], ...)` pattern exactly.
    Reads: `Type`, `NEW_EMP_ID`.
    """
    return get_total_employees(df[df["Type"] == "GCC"])


@cache_on_df
def get_non_gcc_employees(df: pd.DataFrame) -> int:
    """
    `Non GCC Employees` = CALCULATE([Total Employees], Type = "Non GCC").
    Reads: `Type`, `NEW_EMP_ID`.
    """
    return get_total_employees(df[df["Type"] == "Non GCC"])


# --------------------------------------------------------------------------
# Experience
# --------------------------------------------------------------------------


@cache_on_df
def get_average_experience_yrs(df: pd.DataFrame) -> float:
    """
    `Average Experience (Yrs)` — mean of `Total Experience` over active
    headcount (Status == "Active").
    Reads: `Status`, `Total Experience`.
    Edge cases: returns 0.0 if there are no active rows; NaN values in
    `Total Experience` are excluded from the mean by pandas default.
    """
    active = df[df[metric_config.status_column()] == metric_config.status_value("active")]
    if len(active) == 0:
        return 0.0
    return float(active["Total Experience"].mean())


@cache_on_df
def get_average_hexaware_experience(df: pd.DataFrame) -> float:
    """
    `Average Hexaware Experience` — mean of `Hexaware Experience (Years)`
    over active headcount (Status == "Active").
    Reads: `Status`, `Hexaware Experience (Years)`.
    Edge cases: returns 0.0 if there are no active rows.
    """
    active = df[df[metric_config.status_column()] == metric_config.status_value("active")]
    if len(active) == 0:
        return 0.0
    return float(active["Hexaware Experience (Years)"].mean())


# --------------------------------------------------------------------------
# Segmentation
# --------------------------------------------------------------------------


@cache_on_df
def get_pending_mapping_count(df: pd.DataFrame) -> int:
    """
    `Pending Mapping Count` =
        CALCULATE([Total Employees], FILTER('HR Master',
            CONTAINSSTRING(Client as on June 2026, "Client TBD")
            || CONTAINSSTRING(Project Manager, "PM TBD")
            || CONTAINSSTRING(Skill, "Skill TBD")
            || CONTAINSSTRING(DEPUTATION, "Deputation TBD")
            || CONTAINSSTRING(Seniorirty Level, "Seniority TBD")
            || CONTAINSSTRING(Type, "Type TBD")))

    FIXED: previously only checked `Client as on June 2026` / `Project
    Manager`, and was restricted to Active rows. The real DAX checks SIX
    fields and has NO Status filter at all — fixed to match.

    Verified against the real roster file which markers actually occur:
    - `Client as on June 2026` contains "Client TBD": 9 rows -> real marker
    - `Project Manager` contains "PM TBD": 9 rows -> real marker
    - `Seniorirty Level` contains "Seniority TBD": 7 rows -> real marker
    - `Skill` contains "Skill TBD": 0 rows -- FLAG: the `Skill` column's
      actual values (Operations, iOS, Salesforce, QA, Front End, ...)
      never contain "Skill TBD" in the current sample. The DAX assumes
      this pattern exists but it matches zero rows today; this branch is
      effectively a no-op on this dataset, not a bug in the code.
    - `DEPUTATION` contains "Deputation TBD": 0 rows -- FLAG: DEPUTATION
      is currently 100% "OFFSHORE" in this file (also noted in
      data-model SKILL.md), so this branch never fires either.
    - `Type` contains "Type TBD": 0 rows -- FLAG: `Type` is currently
      only ever "GCC"/"Non GCC"; this branch never fires either.
    Net effect: on the current file, only Client/PM/Seniority markers
    contribute, and the combined (OR'd, deduplicated by employee) count
    is 10 (see regression test) -- higher than the previously-implemented
    Active-only, Client/PM-only count of 5, since this also includes
    Inactive rows and Seniority-TBD rows.

    Reads: `Client as on June 2026`, `Project Manager`, `Skill`,
    `DEPUTATION`, `Seniorirty Level`, `Type`, `NEW_EMP_ID`.
    Edge cases: NaN values in any of the six columns are treated as
    non-matching (fillna("") before the substring check).
    """
    fields_markers = [
        (metric_config.column("client"), "Client TBD"),
        ("Project Manager", "PM TBD"),
        ("Skill", "Skill TBD"),
        ("DEPUTATION", "Deputation TBD"),
        ("Seniorirty Level", "Seniority TBD"),
        ("Type", "Type TBD"),
    ]
    mask = pd.Series(False, index=df.index)
    for col, marker in fields_markers:
        mask = mask | df[col].fillna("").astype(str).str.contains(marker, regex=False)
    return get_total_employees(df[mask])


@cache_on_df
def get_clients_covered(df: pd.DataFrame) -> int:
    """
    `Clients Covered` =
        CALCULATE(DISTINCTCOUNT('HR MASTER'[Client as on June 2026]),
            'HR MASTER'[Client as on June 2026] <> BLANK(),
            NOT CONTAINSSTRING(Client as on June 2026, "Client TBD"))

    NEWLY ADDED. Deliberately naive/messy per data-model SKILL.md: counts
    DISTINCT RAW STRING VALUES of `Client as on June 2026`, including
    multi-value cells (e.g. "Managed Services, Scandlines, Inter Milan
    and Blackroll") as ONE distinct value, not four. Do NOT split/clean
    this — replicating the live model's naive count exactly is the goal.
    Reads: `Client as on June 2026`.
    Edge cases: blanks and any value containing "Client TBD" are excluded
    before the distinct count.
    """
    client = df[metric_config.column("client")]
    mask = client.notna() & (~client.astype(str).str.contains("Client TBD", regex=False))
    return int(client[mask].nunique(dropna=True))


@cache_on_df
def get_projects(df: pd.DataFrame) -> int:
    """
    `Projects` (HR MASTER version) = DISTINCTCOUNT('HR MASTER'[Client as
    on June 2026]).

    NEWLY ADDED. NOTE: the real DAX for this measure targets the same
    `Client as on June 2026` column as `Clients Covered` rather than a
    project-name column -- this looks like it may be a copy-paste
    artifact in the source Power BI model (there is no obvious
    project-name column on `HR MASTER` at all; the roster has no
    per-project field, only the messy client field). Replicated exactly
    as given per the task instructions, since that's what the live model
    actually computes -- unlike `Clients Covered`, this does NOT exclude
    blanks or "Client TBD" values (the DAX has no such FILTER).
    Reads: `Client as on June 2026`.
    """
    return evaluate_card(df, "projects")


@cache_on_df
def get_senior_lead_employees(df: pd.DataFrame) -> int:
    """
    `Senior - Lead Employees` =
        CALCULATE([Total Employees], FILTER('HR MASTER',
            CONTAINSSTRING('HR MASTER'[Seniority Levels], "Senior")
            || CONTAINSSTRING('HR MASTER'[Seniority Levels], "Lead")))

    RESOLVED (2026-07-15, confirmed by business owner): the DAX's
    'HR MASTER'[Seniority Levels] (plural, no typo) does not exist as a
    physical column in the real roster file -- only `Seniorirty Level`
    (singular, typo'd) exists. Business owner has confirmed these are the
    same column (a naming inconsistency within the DAX itself, not a
    missing/separate column), so this is implemented against the real
    `Seniorirty Level` column as a confirmed proxy for the DAX's
    `Seniority Levels`. This was previously left unimplemented pending
    exactly this confirmation -- see the (now resolved) note in
    data-model SKILL.md's "Flagged discrepancies" section.

    CONTAINSSTRING is a case-SENSITIVE substring match in DAX (unlike
    SEARCH, which is case-insensitive) -- this implementation matches
    that default exactly: "Senior"/"Lead" with that exact capitalization.

    Verified against the real roster file's `Seniorirty Level` values:
        Standard Lead (12), Premium Senior (8), Standard Senior (8),
        Seniority TBD (7), Premium lead (5), Premium Mid (4),
        Standard Mid (3), Hexa Sr (2), Premium Lead (1),
        Standard senior (1), Premium Technical Service Delivery Manager (1)
    Case-sensitive match on "Senior"/"Lead" hits: Standard Lead (12) +
    Premium Senior (8) + Standard Senior (8) + Premium Lead (1) = 29 rows,
    all with distinct NEW_EMP_ID -> 29.
    NOT matched (case mismatch only): "Premium lead" (5 rows, lowercase
    "lead") and "Standard senior" (1 row, lowercase "senior") -- 6 rows
    total that a case-INsensitive read would additionally include
    (giving 35 instead of 29). This is the same casing-duplicate issue
    already flagged elsewhere in data-model SKILL.md (e.g. "Standard
    senior" vs "Standard Senior" as separate string values). Per
    CONTAINSSTRING's documented case-sensitive default, this
    implementation does NOT fold case and reports 29 -- the 6
    lowercase-variant rows are surfaced as a data-quality warning below
    rather than silently included or excluded either way.
    "Hexa Sr" and "Premium Technical Service Delivery Manager" never
    match either substring under either casing.

    Reads: `Seniorirty Level`, `NEW_EMP_ID`.
    Edge cases: NaN values in `Seniorirty Level` are treated as
    non-matching (fillna("") before the substring check).
    """
    seniority = df["Seniorirty Level"].fillna("").astype(str)
    mask = seniority.str.contains("Senior", case=True, regex=False) | seniority.str.contains(
        "Lead", case=True, regex=False
    )
    return get_total_employees(df[mask])


# --------------------------------------------------------------------------
# Segmentation (cont.) — Strategic Pool / Workforce Category
# --------------------------------------------------------------------------


@cache_on_df
def get_strategic_pool(df: pd.DataFrame) -> int:
    """
    `Strategic Pool` =
        CALCULATE([Total Employees], FILTER('HR MASTER',
            ISBLANK('HR MASTER'[DOJ (DEPT)])))

    FIXED (2026-07-16): previously used `df["DOJ (DEPT)"].isna()` on the
    RAW column, which checks for actual NaN cells only -- the literal
    string "TBD" is not NaN, so this returned 0 on the real file, not the
    reference PDF's 2. That was wrong, not "correct but limited": DAX's
    ISBLANK() operates on the column's value in the data MODEL, and an
    unparseable date literal like "TBD" loaded into a Date-typed column
    in Power BI becomes BLANK() at the model layer (Power BI's import
    step fails to parse it as a date and stores blank) -- it is not a
    literal string surviving into the model the way it does in our raw
    pandas read. The correct pandas equivalent of "blank in the DAX
    model" is therefore the PARSED date column (`_parse_dept_dates`,
    which already turns "TBD" into NaT via `pd.to_datetime(...,
    errors="coerce")`), not the raw string column. Using the parsed
    column now correctly counts the 2 known TBD rows (NEW_EMP_ID
    2000194634, 2000195658) -- returns 2 on the real file, matching the
    Power BI reference. See data-model SKILL.md "Known open data gap"
    (now resolved) for the full root-cause writeup.

    SUPERSEDED (2026-07-21) — now defined as `Status == "Strategic Pool"`.

    The ISBLANK(DOJ (DEPT)) definition above was a proxy that held only
    while the blank-DOJ rows happened to be exactly the rows marked
    Strategic Pool. A roster arrived where they diverged (3 employees
    marked Strategic Pool, only 1 of them with a blank DOJ (DEPT)), so
    Home ("Workforce Category", DOJ-based) showed 1 while HR Home
    ("Status Split", Status-based) showed 3 — the same label reporting
    two different numbers.

    `Status` is the explicit business marker and is now the single
    definition, confirmed by the business owner. Every surface that shows
    "Strategic Pool" routes through THIS function so the two can never
    drift apart again; `metric_invariants.py` asserts that.
    A blank DOJ (DEPT) is incidental missing data, not an intent.
    Reads: `Status`, `NEW_EMP_ID`.
    """
    return evaluate_card(df, "strategic_pool")


@cache_on_df
def get_departments(df: pd.DataFrame) -> int:
    """
    `Departments` = DISTINCTCOUNT('HR MASTER'[Designation ])

    Confirmed real DAX measure. Note the DAX targets `Designation `
    (trailing space in the real model's column reference) -- the source
    Excel column is `Designation` (no trailing space); treated as the
    same column, matching the pattern already established for other
    DAX-vs-source-column naming discrepancies (e.g. `Seniorirty Level`).

    RESOLVED (2026-07-16): a naive `nunique()` on the raw column returned
    30 on the real file, vs. the reference model's 29. Root cause:
    `"SalesForce Core Developer"` (2 rows) vs `"Salesforce Core
    Developer"` (2 rows) is a casing-duplicate data-quality issue in
    `Designation`, identical in nature to the already-handled
    `Seniorirty Level` casing duplicates ("Premium Lead"/"Premium lead"
    etc). Per business-owner decision, the SAME normalize-then-count
    treatment is applied here via `_normalize_designation_label` (a thin
    wrapper around `_normalize_seniority_label`'s title-case approach),
    so the two variants collapse into one distinct value before
    counting. Now returns 29, matching the reference. The underlying
    casing inconsistency is not silently hidden -- see the
    `designation_casing_mismatch` warning in `get_data_quality_warnings`.
    Reads: `Designation`.
    Edge cases: NaN/blank Designation values excluded from the count
    (dropna=True, unchanged).
    """
    return evaluate_card(df, "departments")


@cache_on_df
def get_skills_covered(df: pd.DataFrame) -> int:
    """
    NEWLY ADDED (2026-07-16).

    `Skills Covered` =
    CALCULATE(
        DISTINCTCOUNT('HR Master'[Skill]),
        'HR Master'[Skill] <> BLANK(),
        NOT CONTAINSSTRING('HR Master'[Skill], "TBD")
    )

    Confirmed real DAX measure. Note this targets `Skill` (a broader
    skill-category grouping per data-model SKILL.md), NOT `Primary
    Skill` — the frontend's Skills & Experience page KPI was previously
    wired to distinct-count `Primary Skill` (20 values), which does not
    match this measure or the Power BI reference (16 values). Excludes
    blank/NaN `Skill` values and any value containing the substring
    "TBD" (e.g. a hypothetical "Skill TBD"), even though no current row
    in the real file has a blank or TBD-containing `Skill` value — the
    exclusion filters are implemented per the real DAX for future data.
    Reads: `Skill`.
    Real file: returns 16, matching the Power BI reference exactly.
    """
    skill = df["Skill"]
    mask = skill.notna() & ~skill.astype(str).str.contains("TBD", na=False)
    return int(skill[mask].nunique())


@cache_on_df
def get_workforce_category_split(df: pd.DataFrame) -> dict[str, int]:
    """
    Backs the Main/Home page's "Workforce Category" donut (Active vs
    Strategic Pool).

    Built directly from two CONFIRMED real measures — `get_active_employees`
    (Status == "Active") and `get_strategic_pool` (DOJ (DEPT) is blank) —
    so the values themselves are not provisional. However, the real
    `Home Workforce Category` CALCULATED COLUMN (which presumably encodes
    this exact split as a per-row label) has not had its formula shared,
    so this function is a best-effort reconstruction of what that column
    likely drives, not a replication of the column itself — flagged here
    per the "unconfirmed DAX formula" rule. Since `Active Employees` and
    `Strategic Pool` use different, independent filters (Status vs blank
    DOJ (DEPT)), an employee could in principle satisfy both or neither,
    so these two numbers are NOT guaranteed to sum to `Total Employees`
    — do not assume they're mutually exclusive/exhaustive without the
    real calculated-column formula.
    Reads: (via get_active_employees) `Status`, `NEW_EMP_ID`;
           (via get_strategic_pool) `DOJ (DEPT)`, `NEW_EMP_ID`.

    UPDATE (2026-07-17): as of this date these two numbers DO sum to
    `Closing Headcount` (45 + 2 = 47) for the real roster file, because
    the 2 blank-`DOJ (DEPT)` employees were also given
    `Status = "Strategic Pool"` at the business owner's direction (see
    `get_data_quality_warnings`'s `expected_statuses` set) — so
    `get_active_employees` (Status == "Active") no longer double-counts
    them. This is still not a *structural* guarantee, though: the two
    measures remain independent filters (Status vs blank DOJ (DEPT)), so
    a future row with one but not the other would reintroduce the gap.
    Reads: (via get_active_employees) `Status`, `NEW_EMP_ID`;
           (via get_strategic_pool) `DOJ (DEPT)`, `NEW_EMP_ID`.
    """
    return {
        "Active": get_active_employees(df),
        "Strategic Pool": get_strategic_pool(df),
    }


@cache_on_df
def get_status_split(df: pd.DataFrame) -> dict[str, int]:
    """
    Backs the HR Portal Home "Status Split" donut — full breakdown of the
    `Status` column over the FULL roster (not date-filtered).

    UPDATE (2026-07-17): `Status` now has 3 legitimate values, not 2 —
    "Strategic Pool" was added at the business owner's direction (see
    `get_data_quality_warnings`'s `expected_statuses` set for the full
    rationale). Explicitly enumerating all three here (rather than a
    generic `value_counts()`) keeps this in the same named-getter style
    as the rest of this file and keeps zero-count buckets present in the
    dict even if a future roster snapshot has no Strategic Pool rows.
    Reads: `Status`, `NEW_EMP_ID`.
    """
    return evaluate_chart(df, "status_split")


@cache_on_df
def get_workforce_by_type(df: pd.DataFrame) -> dict[str, int]:
    """
    Backs the "Workforce by Type" / "GCC vs Non-GCC" donuts (Main page
    and Workforce page) — GCC vs Non GCC counts over the full roster,
    wrapping the existing confirmed `get_gcc_employees` /
    `get_non_gcc_employees` measures into dict shape.

    NOTE on ambiguity: the task's reference-page description lists a
    "'GCC vs Non-GCC' donut by Seniority Category" on the Main page,
    which is ambiguous phrasing — it could mean (a) a plain GCC/Non-GCC
    donut (this function), or (b) a GCC/Non-GCC split cross-tabulated
    BY Seniority Category (i.e. a stacked/grouped chart, not a donut).
    This function implements interpretation (a), the simple two-slice
    donut, since "donut" and a 2-value split match `Type` directly and
    the real model has confirmed standalone `GCC Employees`/`Non GCC
    Employees` measures for exactly this. If a Seniority-Category
    cross-tab was actually intended, that's a distinct chart request —
    flagging rather than silently also building a guessed cross-tab.
    Reads: `Type`, `NEW_EMP_ID`.
    """
    return {
        "GCC": get_gcc_employees(df),
        "Non GCC": get_non_gcc_employees(df),
    }


@cache_on_df
def get_headcount_by_region(df: pd.DataFrame) -> dict[str, int]:
    """
    Backs the HR Portal Home "Headcount by Region" bar chart — distinct
    employee count per `Region`, over the FULL roster (no Status/date
    filter), matching `Total Employees`' DISTINCTCOUNT(NEW_EMP_ID)
    semantics per region.

    Verified against the real roster file: EMEA=32, AMER=15, Hexaware=2,
    Region TBD=2, APAC=1 — matches the reference PDF's reported
    breakdown exactly (32 EMEA / 15 AMER / 2 Hexaware / 2 Region TBD /
    1 APAC).
    Reads: `Region`, `NEW_EMP_ID`.
    Edge cases: blank/NaN `Region` values are dropped by `groupby`
    default (none present in the current file).
    """
    return evaluate_chart(df, "headcount_by_region")


@cache_on_df
def get_workforce_by_working_entity(df: pd.DataFrame) -> dict[str, int]:
    """
    Backs the HR Portal Home "Workforce by Working Entity" donut —
    distinct employee count per `Working Entity`, over the full roster.
    Reads: `Working Entity`, `NEW_EMP_ID`.
    Edge cases: blank/NaN values dropped by `groupby` default.
    """
    return evaluate_chart(df, "workforce_by_working_entity")


def _normalize_seniority_label(value: str) -> str:
    """
    Collapse casing-duplicate `Seniorirty Level` values (confirmed in the
    real file: "Premium Lead" vs "Premium lead", "Standard Senior" vs
    "Standard senior") into a single display label, so a chart grouping
    by this label doesn't split one logical category into two bars.

    Normalizes to title-case (e.g. "premium lead" -> "Premium Lead"),
    then restores the "TBD" marker's casing since `str.title()` would
    otherwise turn "Seniority TBD" into "Seniority Tbd" (Python's
    title-casing capitalizes only the first letter of each word).

    This function only affects the DISPLAY grouping key — it does not
    touch the underlying data, and the `seniority_level_casing_mismatch`
    warning in `get_data_quality_warnings()` still surfaces the
    underlying source inconsistency separately.
    """
    return str(value).strip().title().replace("Tbd", "TBD")


def _normalize_designation_label(value: str) -> str:
    """
    Collapse casing-duplicate `Designation` values (confirmed in the real
    file: "SalesForce Core Developer" vs "Salesforce Core Developer") into
    a single display/counting label, using the exact same
    title-case-with-TBD-restore approach as `_normalize_seniority_level`
    (see `_normalize_seniority_label`) for consistency with how this
    codebase already handles this class of bug.

    This only affects the normalized grouping/counting key -- it does not
    touch the underlying data, and the `designation_casing_mismatch`
    warning in `get_data_quality_warnings()` still surfaces the
    underlying source inconsistency separately.
    """
    return _normalize_seniority_label(value)


@cache_on_df
def get_headcount_by_seniority(df: pd.DataFrame) -> dict[str, int]:
    """
    Backs the Workforce page "Headcount by Seniority" bar chart — distinct
    employee count per `Seniorirty Level` value, CASE-NORMALIZED via
    `_normalize_seniority_label` so casing-duplicate source values
    (confirmed: "Premium Lead"/"Premium lead", "Standard Senior"/
    "Standard senior") collapse into one bar instead of splitting a
    single logical category into two. This is distinct from the derived
    Senior/Lead/Mid/Other `Seniority Category` bucketing — see
    `get_workforce_by_seniority_category` for that.

    The underlying casing inconsistency is NOT silently hidden: it is
    still surfaced as-is via the `seniority_level_casing_mismatch`
    warning in `get_data_quality_warnings()`. This function only
    produces a clean, chart-ready breakdown.

    Reads: `Seniorirty Level`, `NEW_EMP_ID`.
    Edge cases: NaN `Seniorirty Level` values are dropped (unchanged
    from prior behavior) rather than folded into a synthetic label.
    """
    normalized = df["Seniorirty Level"].apply(
        lambda v: _normalize_seniority_label(v) if pd.notna(v) else v
    )
    return {
        str(level): get_total_employees(group)
        for level, group in df.groupby(normalized, dropna=True)
    }


# --------------------------------------------------------------------------
# Experience Band (PROVISIONAL — bucket boundaries not confirmed by DAX)
# --------------------------------------------------------------------------

EXPERIENCE_BAND_ORDER = ["0-1 Years", "1-3 Years", "3-5 Years", "5-8 Years", "8+ Years"]


def _experience_band(total_experience: float) -> str:
    """
    PROVISIONAL bucketing of `Total Experience` into the bands shown in
    the reference PDF ("0-1 Years", "1-3 Years", "3-5 Years", "5-8
    Years", "8+ Years"). The real `Experience Band` / `Experience Band
    Sort` calculated columns are confirmed to EXIST on HR MASTER (per
    data-model SKILL.md) but their formula bodies (exact bucket
    boundaries, inclusive/exclusive edges) were NOT provided — this is a
    best-effort guess at the boundaries only, using half-open intervals
    `[lower, upper)` except the last band, and MUST be reconciled against
    the real DAX before being treated as validated.
    """
    if pd.isna(total_experience):
        return "Unknown"
    if total_experience < 1:
        return "0-1 Years"
    if total_experience < 3:
        return "1-3 Years"
    if total_experience < 5:
        return "3-5 Years"
    if total_experience < 8:
        return "5-8 Years"
    return "8+ Years"


@cache_on_df
def get_workforce_by_experience_band(df: pd.DataFrame) -> dict[str, int]:
    """
    PROVISIONAL (see `_experience_band` docstring) — backs both the
    Skills & Experience page's "Total Employees by Experience Band" bar
    chart. Distinct employee count per provisional band, over the full
    roster (`Total Employees` semantics — matches the chart title, no
    Status filter).
    Reads: `Total Experience`, `NEW_EMP_ID`.
    Edge cases: NaN `Total Experience` bucketed into an explicit
    "Unknown" band rather than silently dropped.
    Returned in `EXPERIENCE_BAND_ORDER` (plus "Unknown" if present),
    not alphabetical, so a caller can chart it in the right sequence.
    """
    return evaluate_chart(df, "workforce_by_experience_band")


# --------------------------------------------------------------------------
# Seniority Category (PROVISIONAL — bucket mapping not confirmed by DAX)
# --------------------------------------------------------------------------


def _seniority_category(seniorirty_level: str | float) -> str:
    """
    PROVISIONAL mapping of the raw `Seniorirty Level` string into a
    Senior/Lead/Mid/Other/TBD category. The real `Seniority Category`
    calculated column is confirmed to EXIST on HR MASTER but its formula
    was NOT provided — this is a best-effort guess, using
    case-INsensitive substring matching (deliberately looser than
    `get_senior_lead_employees`'s case-sensitive CONTAINSSTRING, since
    this is a display/grouping bucket, not a replication of that
    specific confirmed measure), and MUST be reconciled against the real
    DAX before being treated as validated.

    Mapping order (first match wins), verified against every distinct
    value in the real file:
      - contains "tbd"                -> "TBD"        (Seniority TBD)
      - contains "lead"                -> "Lead"       (Standard Lead,
                                           Premium lead, Premium Lead)
      - contains "senior" or " sr"     -> "Senior"     (Premium Senior,
                                           Standard Senior, Standard
                                           senior, Hexa Sr)
      - contains "mid"                 -> "Mid"        (Premium Mid,
                                           Standard Mid)
      - anything else                  -> "Other"      (Premium Technical
                                           Service Delivery Manager)

    CONFIG-DRIVEN (2026-07-22): the keyword->band rules now live in
    `configs/roster_metrics.yaml` under `seniority.categories`, so adding
    or reordering a keyword is a config edit, not a code change. Order
    still matters and is preserved from the config: "Seniority TBD"
    contains "senior", so `tbd` is tested first.
    """
    return metric_config.seniority_category(seniorirty_level)


@cache_on_df
def get_workforce_by_seniority_category(df: pd.DataFrame) -> dict[str, int]:
    """
    Backs the Home "Workforce by Seniority" donut and any other
    Senior/Lead/Mid/Other axis referencing "Seniority Category". Bands are
    keyword matches on `Seniorirty Level`, configured in
    `configs/roster_metrics.yaml` (see `_seniority_category`).

    SCOPE (2026-07-22): counts the CURRENT workforce only — the statuses in
    `counts_as_present` (Active + Strategic Pool) — not the full roster.
    A chart titled "Workforce" sitting next to a "Workforce Category" donut
    on the same page must describe the same set of people; showing all 52
    rows here while that donut showed 38 was precisely the kind of
    same-page contradiction this pass exists to remove.
    Reads: `Seniorirty Level`, `Status`, `NEW_EMP_ID`.
    """
    return evaluate_chart(df, "workforce_by_seniority_category")


# --------------------------------------------------------------------------
# Trends across `Available Months` (Month wise Workforce Growth, etc.)
# --------------------------------------------------------------------------


@cache_on_df
def get_month_wise_closing_headcount(df: pd.DataFrame) -> list[dict]:
    """
    Backs the Main/Home "Month wise Workforce Growth" line chart and the
    HR Analytics "Month Wise Headcount" line trend — Closing Headcount
    for every month in the full `Available Months` range
    (`calendar.build_available_months`), reusing `get_closing_headcount`
    per month rather than duplicating its date-filter logic.

    Returns a list of {"month": "Jul 2025", "closing_headcount": int},
    one entry per month, in chronological order (earliest to latest).
    Reads: (via calendar.build_available_months / get_closing_headcount)
    `DOJ (DEPT)`, `LWD`, `Today`, `NEW_EMP_ID`.
    """
    return evaluate_chart(df, "month_wise_headcount")


@cache_on_df
def get_monthly_joiners_vs_leavers(df: pd.DataFrame) -> list[dict]:
    """
    Backs the HR Analytics "Monthly Joiners vs Leavers" bar chart —
    Joiners and Exits for every month in the full `Available Months`
    range, reusing `get_joiners`/`get_exits` per month.

    Returns a list of {"month": "Jul 2025", "joiners": int, "exits": int},
    one entry per month, chronological order.
    Reads: (via get_joiners) `DOJ (DEPT)`, `NEW_EMP_ID`;
           (via get_exits) `LWD`, `NEW_EMP_ID`.
    """
    return evaluate_chart(df, "monthly_joiners_vs_leavers")


@cache_on_df
def get_month_wise_resignation(df: pd.DataFrame) -> list[dict]:
    """
    Backs the HR Analytics drill-down "Month-Wise Resignation" bar
    chart — Exits for every month in the full `Available Months` range.
    Thin wrapper around `get_monthly_joiners_vs_leavers` that drops the
    `joiners` field, kept as a separate named function since it backs a
    visually distinct chart in the reference PDF.
    Reads: (via get_exits) `LWD`, `NEW_EMP_ID`.
    """
    return evaluate_chart(df, "month_wise_resignation")


@cache_on_df
def get_voluntary_involuntary_split(df: pd.DataFrame) -> dict[str, int]:
    """
    Backs the HR Analytics drill-down "Voluntary-Involuntary Split"
    donut — wraps the existing confirmed `get_voluntary_leavers` /
    `get_involuntary_leavers` scalars into dict shape.
    Reads: `Status`, `Reason for Leaving`.
    """
    return evaluate_chart(df, "voluntary_vs_involuntary")


# --------------------------------------------------------------------------
# Exits table (HR Analytics drill-down)
# --------------------------------------------------------------------------

EXITS_TABLE_COLUMNS = {
    "NAME": "name",
    "Designation": "designation",
    "Primary Skill": "primary_skill",
    "Region": "region",
    "Market": "market",
    "Type": "type",
    "LWD": "lwd",
    "Reason for Leaving": "reason_for_leaving",
    "Status": "status",
}


@cache_on_df
def get_exits_table(df: pd.DataFrame) -> list[dict]:
    """
    Backs the HR Analytics drill-down exits data table (NAME,
    Designation, Primary Skill, Region, Market, Type, LWD, Reason for
    Leaving, Status). Filtered to rows with a non-blank `LWD` (i.e. any
    row that has ever had a last working day recorded), NOT strictly
    `Status == "Inactive"` — per data-model SKILL.md, `LWD` is confirmed
    "only populated when Status = Inactive", so in practice these two
    filters should coincide, but filtering on `LWD` directly is more
    faithful to "who has exited" than trusting `Status` alone (and rows
    where the two disagree would already be worth a
    `unexpected_status_value`-style investigation, not silently masked
    here).

    Cleaned display column names per `EXITS_TABLE_COLUMNS` (source names
    kept exactly through the whole rest of this module; renaming happens
    only at this output-layer boundary). `NAME` is whitespace-trimmed
    (known double-space gotcha in source data per data-model SKILL.md).
    Reads: `NAME`, `Designation`, `Primary Skill`, `Region`, `Market`,
    `Type`, `LWD`, `Reason for Leaving`, `Status`.
    Edge cases: blank `LWD` rows excluded; `LWD` is returned as the raw
    source string (date formatting/parsing is left to the caller/API
    layer, consistent with this module keeping source values as-is).
    """
    exited = df[df[metric_config.column("leaving_date")].notna()]
    records = []
    for _, row in exited.iterrows():
        record = {}
        for src_col, out_key in EXITS_TABLE_COLUMNS.items():
            value = row.get(src_col)
            if src_col == "NAME" and isinstance(value, str):
                value = " ".join(value.split())
            record[out_key] = value
        records.append(record)
    return records


# --------------------------------------------------------------------------
# Skill bifurcation (stacked-bar cross-tabs) — Skills & Experience page
# --------------------------------------------------------------------------


def _skill_crosstab(df: pd.DataFrame, dimension: pd.Series, dimension_name: str) -> list[dict]:
    """
    Shared helper: distinct-employee cross-tab of `Primary Skill` x an
    arbitrary categorical `dimension` Series (same index as `df`).
    Returns a flat list of {"primary_skill": ..., dimension_name: ...,
    "count": int} rows (long format), which is what Tremor/Recharts
    stacked-bar components consume directly (one row per
    skill/dimension-value combination).
    """
    skill = df["Primary Skill"]
    grouped = df.assign(_dimension=dimension).groupby(
        [skill, "_dimension"], dropna=True
    )["NEW_EMP_ID"].nunique()
    return [
        {"primary_skill": str(skill_val), dimension_name: str(dim_val), "count": int(count)}
        for (skill_val, dim_val), count in grouped.items()
        if count > 0
    ]


@cache_on_df
def get_skill_bifurcation_by_experience_band(df: pd.DataFrame) -> list[dict]:
    """
    PROVISIONAL (inherits `_experience_band`'s unconfirmed bucket
    boundaries) — backs the Skills & Experience "Skill Bifurcation by
    Experience" stacked bar (Primary Skill x Experience Band).
    Reads: `Primary Skill`, `Total Experience`, `NEW_EMP_ID`.
    """
    bands = df["Total Experience"].apply(_experience_band)
    return _skill_crosstab(df, bands, "experience_band")


@cache_on_df
def get_skill_bifurcation_by_seniority_category(df: pd.DataFrame) -> list[dict]:
    """
    PROVISIONAL (inherits `_seniority_category`'s unconfirmed mapping) —
    backs the Skills & Experience "Skill Bifurcation by Seniority"
    stacked bar (Primary Skill x Seniority Category).
    Reads: `Primary Skill`, `Seniorirty Level`, `NEW_EMP_ID`.
    """
    categories = df["Seniorirty Level"].apply(_seniority_category)
    return _skill_crosstab(df, categories, "seniority_category")


@cache_on_df
def get_skill_bifurcation_by_region(df: pd.DataFrame) -> list[dict]:
    """
    Backs the Skills & Experience "Skill Bifurcation by Region" stacked
    bar (Primary Skill x Region). Not provisional — `Region` is a
    confirmed real source column, unlike the Experience Band / Seniority
    Category groupings.
    Reads: `Primary Skill`, `Region`, `NEW_EMP_ID`.
    """
    return _skill_crosstab(df, df["Region"], "region")


# --------------------------------------------------------------------------
# Workforce Details by Region (small multiples) — Workforce page
# --------------------------------------------------------------------------


@cache_on_df
def get_workforce_details_by_region(df: pd.DataFrame) -> list[dict]:
    """
    Backs the Workforce page "Workforce Details by Region" small
    multiples (one bar chart per region). AMBIGUOUS chart content — the
    reference page description doesn't specify what dimension each
    per-region bar breaks down BY (only that it's "small multiples bar
    per region"). Rather than block this entirely, this implements the
    most likely reading (a per-region breakdown by provisional Seniority
    Category, since the Workforce page's other two charts already cover
    Type and raw Seniority) and flags it explicitly here and in the
    handoff notes — CONFIRM the intended second dimension (Seniority
    Category vs Grade vs Type vs something else) with the business
    owner/reference PDF before treating this as final; do not assume
    this guess is correct.
    Returns a flat list of {"region": ..., "seniority_category": ...,
    "count": int} rows (long format, same shape as the skill-bifurcation
    cross-tabs above).
    Reads: `Region`, `Seniorirty Level`, `NEW_EMP_ID`.
    """
    categories = df["Seniorirty Level"].apply(_seniority_category)
    region = df["Region"]
    grouped = df.assign(_category=categories).groupby(
        [region, "_category"], dropna=True
    )["NEW_EMP_ID"].nunique()
    return [
        {"region": str(region_val), "seniority_category": str(cat_val), "count": int(count)}
        for (region_val, cat_val), count in grouped.items()
        if count > 0
    ]


# --------------------------------------------------------------------------
# Employee Directory — full cleaned roster list
# --------------------------------------------------------------------------

EMPLOYEE_DIRECTORY_COLUMNS = {
    "NEW_EMP_ID": "employee_id",
    "NAME": "name",
    "GRADE": "grade",
    "Designation": "designation",
    "WORK_LOCATION": "work_location",
    "Total Experience": "total_experience",
    "Designation": "designation",
    "Working Entity": "working_entity",
    "Client": "client",
    "Seniorirty Level": "seniority_level",
    "Region": "region",
    "Market": "market",
    "Status": "status",
    "Type": "type",
    "Primary Skill": "primary_skill",
    "Skill": "skill",
    "SUPERVISOR (Hexaware)": "supervisor",
}


@cache_on_df
def get_employee_directory(df: pd.DataFrame) -> list[dict]:
    """
    Backs the Employee Directory page's full searchable/paginated table.
    Returns the FULL cleaned roster as a list of employee records (no
    pagination — that's api-agent's job per api-conventions SKILL.md's
    Excel/DB swap boundary; this function just returns everything).

    Cleaned display column names per `EMPLOYEE_DIRECTORY_COLUMNS`
    (source names kept exactly through the rest of this module; renamed
    only at this output-layer boundary, per module docstring). `NAME`
    and `SUPERVISOR (Hexaware)` are whitespace-trimmed (known
    double-space gotcha between first/last name in source data, per
    data-model SKILL.md).
    Reads: `NEW_EMP_ID`, `NAME`, `GRADE`, `Designation`, `WORK_LOCATION`,
    `Total Experience`, `Working Entity`, `Client as on June 2026`,
    `Seniorirty Level`, `Region`, `Market`, `Status`, `Type`,
    `Primary Skill`, `Skill`, `SUPERVISOR (Hexaware)`.
    Edge cases: does NOT split the multi-value `Client as on June 2026`
    field (per data-model SKILL.md's explicit multi-value handling
    rule) — returned as the raw free-text string for display/filtering.
    """
    records = []
    for _, row in df.iterrows():
        record = {}
        for src_col, out_key in EMPLOYEE_DIRECTORY_COLUMNS.items():
            value = row.get(src_col)
            if src_col in ("NAME", "SUPERVISOR (Hexaware)") and isinstance(value, str):
                value = " ".join(value.split())
            record[out_key] = value
        records.append(record)
    return records


# --------------------------------------------------------------------------
# BLOCKED — do not implement without human confirmation
# --------------------------------------------------------------------------
#
# Utilization-percentage measures (`Weekly Utilization %` and friends):
#
#   Confirmed none exist in this module (roster_metrics.py) or in
#   booking_metrics.py. Per data-model SKILL.md's "Flagged
#   discrepancies" section, `Weekly Utilization %` and
#   `Period Total Utilization %` are calculated columns on
#   `UtilizationLongTable` whose formula bodies are still missing (only
#   measures were exported) -- out of scope until those two formulas are
#   provided, left untouched in this reconciliation pass.


# --------------------------------------------------------------------------
# Server-side filtering — one implementation, shared by every filtered page
# --------------------------------------------------------------------------


def apply_filters(df: pd.DataFrame, selected: dict[str, str] | None) -> pd.DataFrame:
    """
    Narrow the roster by the page filters declared in
    `configs/roster_metrics.yaml` under `filters:`.

    Exists so a filtered page can ask the API for its numbers instead of
    recomputing them in the browser. Each HR page used to re-implement
    these filters client-side against hardcoded strings
    (`status === 'Active'`), which quietly duplicated every metric
    definition: rename a status in config and the backend followed while
    those pages did not. Filtering here means the page and the API can
    only ever agree, because there is one implementation.

    Unknown filter names and blank/"all" selections are ignored.
    """
    if not selected:
        return df

    declared = metric_config.filters()
    out = df
    for name, value in selected.items():
        if not value or name not in declared:
            continue
        spec = declared[name]

        # A filter can be a plain column, or a DERIVED bucket reusing a
        # chart's own definition (e.g. "Experience = 5-8 Years"), so the
        # filter and the chart it filters can never use different rules.
        chart_name = spec.get("derived_from_chart")
        if chart_name:
            labels = chart_labels(out, metric_config.chart(chart_name))
            out = out[labels.astype(str) == str(value)]
            continue

        column = metric_config.column(spec["column_role"])
        if column not in out.columns:
            continue
        out = out[out[column].astype(str) == str(value)]
    return out
