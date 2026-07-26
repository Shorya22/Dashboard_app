"""
Loader for the roster METRIC semantics config.

Keeps business meaning (which status counts as present, which words map to
a seniority band) out of Python and in versioned YAML, so changing it is a
config edit rather than a code change + redeploy.

This is deliberately narrow — it configures the handful of business
policies that actually vary, not a general metric DSL. Date-window
measures (Joiners, Exits, Attrition) still live in code because their
logic is genuinely algorithmic, not a value list.
"""

from __future__ import annotations

import functools
from pathlib import Path

import pandas as pd
import yaml

CONFIG_DIR = Path(__file__).resolve().parent / "configs"


@functools.lru_cache(maxsize=None)
def load_metric_config(dataset: str = "roster") -> dict:
    """Load and cache a dataset's metric-semantics config."""
    path = CONFIG_DIR / f"{dataset}_metrics.yaml"
    with path.open("r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    validate_metric_config(cfg, dataset)
    return cfg


# --- booking ------------------------------------------------------------- #
def booking_columns() -> dict[str, str]:
    """The booking `columns:` block — column role -> physical column name.

    Mirrors the roster's implicit `load_metric_config()["columns"]` access.
    """
    return load_metric_config("booking").get("columns", {})


def booking_column(role: str) -> str:
    """Physical column for a booking role.

    Resolves in this order:
      1. The `columns:` block (region, market, department, entity, holding,
         hours_type, week_start, month) — added in Phase 3.
      2. The legacy `hours:` block for `hours_type` / `hours_value` — kept
         so existing callers keep working without changes.
    """
    cols = booking_columns()
    if role in cols:
        return cols[role]
    return {
        "hours_type": hours_type_column(),
        "hours_value": hours_value_column(),
    }[role]


def booking_chart(name: str) -> dict:
    return load_metric_config("booking")["charts"][name]


def booking_card(name: str) -> dict:
    """A Utilization-side card's declarative definition — drives
    `booking_metrics.evaluate_booking_card`. Same shape as the roster's
    `card(name)`, keyed off `booking_metrics.yaml`."""
    return load_metric_config("booking")["cards"][name]


def booking_card_names() -> list[str]:
    return list(load_metric_config("booking").get("cards", {}))


def booking_chart_names() -> list[str]:
    return list(load_metric_config("booking").get("charts", {}))


def hours_label(key: str) -> str:
    """Look up a named entry in the booking `hours:` block (client_label,
    internal_label). Cards with a `filter_label_key` resolve their filter
    literal here, so renaming a hours category is a one-line change."""
    return load_metric_config("booking")["hours"][key]


def hours_value_column() -> str:
    return load_metric_config("booking")["hours"]["value_column"]


def hours_type_column() -> str:
    return load_metric_config("booking")["hours"]["type_column"]


def client_hours_label() -> str:
    return load_metric_config("booking")["hours"]["client_label"]


def internal_hours_label() -> str:
    return load_metric_config("booking")["hours"]["internal_label"]


# --- roster: column roles ------------------------------------------------- #
def column(role: str) -> str:
    """
    The physical column playing a business role (e.g. "employee_id").

    Metrics refer to roles rather than raw headings, so a renamed source
    column is a one-line config change. Relevant for `client`, whose real
    heading ("Client as on June 2026") is expected to drift each period.
    """
    return load_metric_config()["columns"][role]


def employee_id_column() -> str:
    return column("employee_id")


def card(name: str) -> dict:
    """A card's declarative definition — drives `evaluate_card`."""
    return load_metric_config()["cards"][name]


def chart(name: str) -> dict:
    """A chart's declarative definition — drives `evaluate_chart`."""
    return load_metric_config()["charts"][name]


def chart_names() -> list[str]:
    return list(load_metric_config()["charts"])


def leaving_reason(kind: str) -> str:
    """A configured leaving-reason value, e.g. leaving_reason("voluntary")."""
    return load_metric_config()["attrition"]["reasons"][kind]


def directory_fields() -> dict[str, str]:
    """Directory record: output key -> column role."""
    return load_metric_config()["directory"]["fields"]


def directory_columns() -> list[dict]:
    """Ordered display columns for the directory table (key + label + hints)."""
    return load_metric_config()["directory"]["columns"]


def directory_trim_keys() -> list[str]:
    return load_metric_config()["directory"].get("trim_whitespace", [])


def filters(dataset: str = "roster") -> dict[str, dict]:
    """The declared page filters, keyed by filter name.

    `dataset` defaults to "roster" so existing callers (e.g. the roster
    `_filter_params` dependency) keep working. Pass "booking" for the
    Utilization-side filter definitions.
    """
    return load_metric_config(dataset).get("filters", {})


# --- roster: status ------------------------------------------------------- #
def status_column() -> str:
    return column("status")


def status_value(key: str) -> str:
    """A named status literal, e.g. status_value("strategic_pool")."""
    return load_metric_config()["status"][key]


def present_statuses() -> list[str]:
    """
    Statuses that count as "currently part of the workforce".

    Every present-headcount surface scopes to exactly this list, so the
    Closing Headcount KPI, the month-wise growth trend and the workforce
    composition charts cannot disagree about who is here.
    """
    return list(load_metric_config()["status"]["counts_as_present"])


def is_present(df: pd.DataFrame) -> pd.Series:
    """Boolean mask of rows whose Status counts as currently present."""
    return df[status_column()].isin(present_statuses())


def seniority_column() -> str:
    return column("seniority")


def seniority_category(value: object) -> str:
    """
    Map a raw seniority string to its band via the configured keyword
    rules (first match wins, case-insensitive substring).
    """
    cfg = load_metric_config()["seniority"]
    if pd.isna(value):
        return cfg["missing_label"]
    text = str(value).lower()
    for rule in cfg["categories"]:
        if rule["contains"].lower() in text:
            return rule["label"]
    return cfg["default_label"]


# ---------------------------------------------------------------------------
# Config self-validation
# ---------------------------------------------------------------------------
# The metric config is edited by hand, so a typo is likely. Without this a
# mistake surfaces as a KeyError mid-request — a 500 for whoever happens to
# open that page, with a stack trace instead of an explanation. These checks
# run once when the config is loaded and name the exact problem.

SUPPORTED_CHART_TYPES = {
    "count_by",
    "numeric_bands",
    "keyword_bands",
    "monthly_series",
    "crosstab",
    "sum_by",
    # Two-level group-by: primary + secondary group column, summing a value
    # column. Backs the Utilization Home "Total Hours by Region / Market"
    # chart, which needs region+market pairs rather than a flat group-by.
    "sum_by_hierarchical",
    # `sum_by` variant that returns a projected `list[{group, split_1: v,
    # split_2: v, ...}]` shape rather than a raw pivot table. Powers the
    # Employee/Project drill-through charts so the endpoint doesn't need a
    # per-chart Python reshape. Added 2026-07-26.
    "sum_by_split",
    # Per-group aggregate-then-ratio: sum(numerator)/sum(denominator) within
    # each group. Backs the Overview page's Weekly Utilization Trend and
    # Employee Period Utilization ranking (Formula A) — both booking-derived
    # after Overview stopped consuming the ground-truth file at runtime.
    "ratio_by",
    # First-match-wins bands over the values of a `ratio_by` chart — same
    # `below` semantics as `numeric_bands`; catch-all last band. Powers the
    # Overview page's Utilization Split donut (high/moderate/low bins over
    # per-employee Formula A ratios).
    "ratio_bands",
    # `avg_of_group_ratios`: for each outer_group value, compute a
    # `ratio_by(inner_group)` on that subframe and return the mean of the
    # per-inner-group ratios. Backs the Overview page's Weekly Utilization
    # Trend under D1a semantics (mean of per-employee-ratios per week),
    # which differs from `ratio_by(week_start)` (aggregate-then-ratio at
    # the whole-week level).
    "avg_of_group_ratios",
}
SUPPORTED_SCOPES = {"all", "present", "exited"}
SUPPORTED_MEASURES = {"closing_headcount"}
SUPPORTED_FILTER_TYPES = {"single", "multi", "hierarchical"}
# Utilization-side card measures. Every booking card declares one of these,
# so the compute is dispatched from the declaration rather than a bespoke
# function per card (mirrors the roster's `counts: distinct` contract).
# `ratio` and `avg_of_chart` were added 2026-07-26 for the Overview page's
# booking-derived KPIs (see METRICS.md Page 8):
#   * ratio          — generic (numerator / denominator), optionally filtered
#                      per side. Scalar output.
#   * avg_of_chart   — mean over the values of a declared chart's output.
#                      Composes with `ratio_by` for "avg of per-employee
#                      ratios" without a bespoke Python function.
SUPPORTED_BOOKING_CARD_MEASURES = {
    "distinct_count",
    "sum",
    "count_rows",
    "mean",
    "ratio",
    "avg_of_chart",
}
# `filter_scope` is documentary only — the dispatcher never filters on this.
# It records which slice the caller must pass in: `filtered` = the endpoint
# already narrowed the frame by the page's filter row; `whole_scope` = the
# endpoint hands in the full drill-through scope (an Employee's or a
# Holding's rows) and page-local filters (Hours Type, Project, Week,
# Employee-on-project) narrow only the charts, not the KPI.
SUPPORTED_FILTER_SCOPES = {"filtered", "whole_scope"}


class MetricConfigError(ValueError):
    """Raised for a malformed metric config — a developer error, not user data."""


def validate_metric_config(cfg: dict, dataset: str = "roster") -> None:
    """Fail loudly, at load time, with a message that says what to fix."""
    problems: list[str] = []
    roles = dict(cfg.get("columns", {}))
    # Booking's `hours:` block predates the `columns:` block; the two
    # `sum_by` chart roles (`hours_type`, `hours_value`) resolve there
    # rather than in `columns:`. Include them so role validation passes
    # without forcing a duplicate declaration.
    if dataset == "booking":
        hours_block = cfg.get("hours", {})
        if "type_column" in hours_block:
            roles.setdefault("hours_type", hours_block["type_column"])
        if "value_column" in hours_block:
            roles.setdefault("hours_value", hours_block["value_column"])
    charts = cfg.get("charts", {})
    statuses = cfg.get("status", {})

    def need_role(role: object, where: str) -> None:
        if role not in roles:
            problems.append(
                f"{where}: column_role {role!r} is not defined in `columns:` "
                f"(known: {sorted(roles)})"
            )

    for name, card in cfg.get("cards", {}).items():
        # `column_role` is required for the column-based measure types
        # (distinct_count / sum / count_rows / mean); `ratio` uses
        # numerator_column_role + denominator_column_role, and `avg_of_chart`
        # uses `from_chart` — both check their own roles below.
        measure_type_precheck = card.get("measure_type", "distinct_count")
        if measure_type_precheck not in ("ratio", "avg_of_chart"):
            need_role(card.get("column_role"), f"cards.{name}")
        # Booking cards declare a measure_type (distinct_count / sum /
        # count_rows) and optionally a filter_column_role + filter_label_key
        # (the label_key resolves through the `hours:` block, so the
        # client/internal literals live in one place). Roster cards
        # continue to declare `counts: distinct` — treated as the
        # distinct_count default here so the roster YAML doesn't need to
        # change.
        if dataset == "booking":
            measure_type = measure_type_precheck
            if measure_type not in SUPPORTED_BOOKING_CARD_MEASURES:
                problems.append(
                    f"cards.{name}: measure_type {measure_type!r} is not implemented "
                    f"(supported: {sorted(SUPPORTED_BOOKING_CARD_MEASURES)})"
                )
            # `filter_scope` is documentary — every booking card should state
            # which slice the caller passes in so the declaration explains
            # itself. Not required (default = filtered) so existing declarations
            # don't have to be touched, but if present it must be a known value.
            fscope = card.get("filter_scope")
            if fscope is not None and fscope not in SUPPORTED_FILTER_SCOPES:
                problems.append(
                    f"cards.{name}: filter_scope {fscope!r} is not supported "
                    f"(supported: {sorted(SUPPORTED_FILTER_SCOPES)})"
                )
            hours_block = cfg.get("hours", {})
            # `ratio` needs a numerator+denominator role, each optionally
            # filtered against an hours-block label key. `avg_of_chart` needs
            # a from_chart declaring which chart's values to mean.
            if measure_type == "ratio":
                for side in ("numerator_column_role", "denominator_column_role"):
                    need_role(card.get(side), f"cards.{name}")
                for side, label_key in (
                    ("numerator_filter_column_role", "numerator_filter_label_key"),
                    ("denominator_filter_column_role", "denominator_filter_label_key"),
                ):
                    if side in card:
                        need_role(card.get(side), f"cards.{name}")
                        key = card.get(label_key)
                        if key is None:
                            problems.append(
                                f"cards.{name}: {side} is set but {label_key} is missing"
                            )
                        elif key not in hours_block:
                            problems.append(
                                f"cards.{name}: {label_key} {key!r} is not in `hours:` "
                                f"(known: {sorted(hours_block)})"
                            )
            elif measure_type == "avg_of_chart":
                from_chart = card.get("from_chart")
                if from_chart is None:
                    problems.append(
                        f"cards.{name}: avg_of_chart needs `from_chart`"
                    )
                elif from_chart not in cfg.get("charts", {}):
                    problems.append(
                        f"cards.{name}: from_chart {from_chart!r} is not a declared chart "
                        f"(known: {sorted(cfg.get('charts', {}))})"
                    )
                scope_role = card.get("scope_to_latest_of_role")
                if scope_role is not None:
                    need_role(scope_role, f"cards.{name}")
            filter_role = card.get("filter_column_role")
            if filter_role is not None:
                need_role(filter_role, f"cards.{name}")
                key = card.get("filter_label_key")
                if key is None:
                    problems.append(
                        f"cards.{name}: filter_column_role is set but filter_label_key "
                        "is missing — the card can't resolve which value to filter on"
                    )
                elif key not in hours_block:
                    problems.append(
                        f"cards.{name}: filter_label_key {key!r} is not declared in "
                        f"the `hours:` block (known: {sorted(hours_block)})"
                    )
        status_filter = card.get("status_filter", "none")
        if status_filter not in ("none", None, "present") and status_filter not in statuses:
            problems.append(
                f"cards.{name}: status_filter {status_filter!r} is not a status "
                f"declared in `status:` (known: "
                f"{sorted(k for k in statuses if k != 'counts_as_present')})"
            )

    for name, chart in charts.items():
        kind = chart.get("type")
        if kind not in SUPPORTED_CHART_TYPES:
            problems.append(
                f"charts.{name}: type {kind!r} is not implemented "
                f"(supported: {sorted(SUPPORTED_CHART_TYPES)})"
            )
        scope = chart.get("scope", "all")
        if scope not in SUPPORTED_SCOPES:
            problems.append(
                f"charts.{name}: scope {scope!r} is not supported "
                f"(supported: {sorted(SUPPORTED_SCOPES)})"
            )
        if kind == "monthly_series":
            for i, series in enumerate(chart.get("series", [])):
                if "key" not in series:
                    problems.append(f"charts.{name}.series[{i}]: missing `key`")
                has = [k for k in ("measure", "date_role") if k in series]
                if len(has) != 1:
                    problems.append(
                        f"charts.{name}.series[{i}]: needs exactly one of "
                        f"`measure` or `date_role` (found {has or 'neither'})"
                    )
                if "date_role" in series:
                    need_role(series["date_role"], f"charts.{name}.series[{i}]")
                if series.get("measure") and series["measure"] not in SUPPORTED_MEASURES:
                    problems.append(
                        f"charts.{name}.series[{i}]: measure "
                        f"{series['measure']!r} is not implemented "
                        f"(supported: {sorted(SUPPORTED_MEASURES)})"
                    )
        elif kind == "sum_by":
            need_role(chart.get("group_column_role"), f"charts.{name}")
            need_role(chart.get("value_column_role"), f"charts.{name}")
            # Optional second dimension: sum is pivoted across this
            # column's values (e.g. Weekly Hours Trend groups by week and
            # splits each week across Client / Internal hours types).
            split = chart.get("split_column_role")
            if split is not None:
                need_role(split, f"charts.{name}")
        elif kind == "sum_by_hierarchical":
            need_role(chart.get("primary_group_role"), f"charts.{name}")
            need_role(chart.get("secondary_group_role"), f"charts.{name}")
            need_role(chart.get("value_column_role"), f"charts.{name}")
        elif kind == "sum_by_split":
            # Same three roles as `sum_by` with a split, but the dispatcher
            # returns the projected list-of-dicts shape rather than the raw
            # pivot table so the endpoint doesn't need a per-chart reshape.
            need_role(chart.get("group_column_role"), f"charts.{name}")
            need_role(chart.get("value_column_role"), f"charts.{name}")
            need_role(chart.get("split_column_role"), f"charts.{name}")
        elif kind == "ratio_by":
            need_role(chart.get("group_column_role"), f"charts.{name}")
            for side in ("numerator_column_role", "denominator_column_role"):
                need_role(chart.get(side), f"charts.{name}")
            hours_block = cfg.get("hours", {})
            for side, label_key in (
                ("numerator_filter_column_role", "numerator_filter_label_key"),
                ("denominator_filter_column_role", "denominator_filter_label_key"),
            ):
                if side in chart:
                    need_role(chart.get(side), f"charts.{name}")
                    key = chart.get(label_key)
                    if key is None:
                        problems.append(
                            f"charts.{name}: {side} is set but {label_key} is missing"
                        )
                    elif key not in hours_block:
                        problems.append(
                            f"charts.{name}: {label_key} {key!r} is not in `hours:` "
                            f"(known: {sorted(hours_block)})"
                        )
            aggregate = chart.get("aggregate", "per_group")
            if aggregate not in {"per_group"}:
                problems.append(
                    f"charts.{name}: ratio_by aggregate {aggregate!r} is not supported "
                    "(supported: ['per_group'])"
                )
        elif kind == "avg_of_group_ratios":
            for role in ("outer_group_role", "inner_group_role",
                         "numerator_column_role", "denominator_column_role"):
                need_role(chart.get(role), f"charts.{name}")
            hours_block = cfg.get("hours", {})
            for side, label_key in (
                ("numerator_filter_column_role", "numerator_filter_label_key"),
                ("denominator_filter_column_role", "denominator_filter_label_key"),
            ):
                if side in chart:
                    need_role(chart.get(side), f"charts.{name}")
                    key = chart.get(label_key)
                    if key is None:
                        problems.append(
                            f"charts.{name}: {side} is set but {label_key} is missing"
                        )
                    elif key not in hours_block:
                        problems.append(
                            f"charts.{name}: {label_key} {key!r} is not in `hours:` "
                            f"(known: {sorted(hours_block)})"
                        )
        elif kind == "ratio_bands":
            ratio_ref = chart.get("ratio_from_chart")
            if ratio_ref not in charts:
                problems.append(
                    f"charts.{name}: ratio_from_chart {ratio_ref!r} is not a declared chart "
                    f"(known: {sorted(charts)})"
                )
            elif charts[ratio_ref].get("type") != "ratio_by":
                problems.append(
                    f"charts.{name}: ratio_from_chart {ratio_ref!r} must be type `ratio_by` "
                    f"(got {charts[ratio_ref].get('type')!r})"
                )
            bands = chart.get("bands", [])
            if not bands:
                problems.append(f"charts.{name}: ratio_bands needs `bands`")
            for i, band in enumerate(bands[:-1]):
                if "below" not in band:
                    problems.append(
                        f"charts.{name}.bands[{i}]: only the LAST band may omit `below` "
                        "(catch-all); an earlier one without it would swallow every "
                        "remaining value"
                    )
            if bands and "below" in bands[-1]:
                problems.append(
                    f"charts.{name}: the last band must omit `below` so values "
                    "above the final threshold still land somewhere"
                )
        elif kind == "crosstab":
            need_role(chart.get("row_column_role"), f"charts.{name}")
            dim = chart.get("dimension_from_chart")
            if dim not in charts:
                problems.append(
                    f"charts.{name}: dimension_from_chart {dim!r} is not a "
                    f"declared chart (known: {sorted(charts)})"
                )
            for key in ("row_key", "dimension_key"):
                if key not in chart:
                    problems.append(f"charts.{name}: crosstab needs `{key}`")
        else:
            need_role(chart.get("column_role"), f"charts.{name}")

        if kind == "numeric_bands":
            bands = chart.get("bands", [])
            if not bands:
                problems.append(f"charts.{name}: numeric_bands needs `bands`")
            for i, band in enumerate(bands[:-1]):
                if "below" not in band:
                    problems.append(
                        f"charts.{name}.bands[{i}]: only the LAST band may omit "
                        "`below` (it is the catch-all); an earlier one without it "
                        "would swallow every remaining value"
                    )
            if bands and "below" in bands[-1]:
                problems.append(
                    f"charts.{name}: the last band must omit `below` so values "
                    "above the final threshold still land somewhere"
                )

    filters_block = cfg.get("filters", {})
    for name, spec in filters_block.items():
        chart_ref = spec.get("derived_from_chart")
        # `time_filter: true` marks a filter whose values are month labels
        # ("Mon YYYY"), not raw column values — `apply_filters` narrows
        # to rows active in any of the selected months (see
        # `_apply_month_year_filter` in roster_metrics). No `column_role`
        # / `derived_from_chart` needed because no single column carries
        # those month strings.
        if spec.get("time_filter"):
            pass
        elif chart_ref is not None:
            if chart_ref not in charts:
                problems.append(
                    f"filters.{name}: derived_from_chart {chart_ref!r} is not a "
                    f"declared chart (known: {sorted(charts)})"
                )
        else:
            need_role(spec.get("column_role"), f"filters.{name}")
        ftype = spec.get("type")
        if ftype is not None and ftype not in SUPPORTED_FILTER_TYPES:
            problems.append(
                f"filters.{name}: type {ftype!r} is not supported "
                f"(supported: {sorted(SUPPORTED_FILTER_TYPES)})"
            )
        nests = spec.get("nests")
        if nests is not None and nests not in filters_block:
            problems.append(
                f"filters.{name}: nests {nests!r} is not a declared filter key "
                f"(known: {sorted(filters_block)})"
            )
        pages = spec.get("applies_to_pages")
        if pages is not None:
            if not isinstance(pages, list) or not all(isinstance(p, str) for p in pages):
                problems.append(
                    f"filters.{name}: applies_to_pages must be a list of strings"
                )
        # `order` (display order in the frontend filter grid) and
        # `searchable` (opt-in dropdown search input) are optional YAML-level
        # widget-metadata fields. They are strictly typed here so a stray
        # `searchable: "yes"` or `order: "1"` fails at load time rather
        # than silently misbehaving on the frontend (which would coerce a
        # string "0" to a truthy value under `+Infinity`-style sort keys).
        # `isinstance(bool, int)` is True in Python, so screen booleans
        # out of the `order` check explicitly.
        if "order" in spec:
            order = spec["order"]
            if isinstance(order, bool) or not isinstance(order, int):
                problems.append(
                    f"filters.{name}: order must be an integer (got {type(order).__name__})"
                )
        if "searchable" in spec:
            searchable = spec["searchable"]
            if not isinstance(searchable, bool):
                problems.append(
                    f"filters.{name}: searchable must be a boolean (got {type(searchable).__name__})"
                )

    declared_status_values = {
        v for k, v in statuses.items() if k != "counts_as_present"
    }
    for value in statuses.get("counts_as_present", []):
        if value not in declared_status_values:
            problems.append(
                f"status.counts_as_present: {value!r} is not one of the declared "
                f"status values ({sorted(declared_status_values)}) — headcount "
                "would silently exclude it"
            )

    directory = cfg.get("directory", {})
    field_keys = set(directory.get("fields", {}))
    for key, role in directory.get("fields", {}).items():
        need_role(role, f"directory.fields.{key}")
    for i, colspec in enumerate(directory.get("columns", [])):
        if "key" not in colspec or "label" not in colspec:
            problems.append(f"directory.columns[{i}]: needs `key` and `label`")
            continue
        # every display column except the synthetic serial must map to a field
        if colspec.get("display") != "serial" and colspec["key"] not in field_keys:
            problems.append(
                f"directory.columns[{i}]: key {colspec['key']!r} is not a "
                f"directory field (known: {sorted(field_keys)})"
            )
    for key in directory.get("trim_whitespace", []):
        if key not in field_keys:
            problems.append(
                f"directory.trim_whitespace: {key!r} is not a directory field"
            )

    for i, rule in enumerate(cfg.get("seniority", {}).get("categories", [])):
        missing = [k for k in ("contains", "label") if k not in rule]
        if missing:
            problems.append(f"seniority.categories[{i}]: missing {missing}")

    if problems:
        raise MetricConfigError(
            f"{dataset}_metrics.yaml is invalid:\n  - " + "\n  - ".join(problems)
        )
