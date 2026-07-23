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
}
SUPPORTED_SCOPES = {"all", "present", "exited"}
SUPPORTED_MEASURES = {"closing_headcount"}
SUPPORTED_FILTER_TYPES = {"single", "multi", "hierarchical"}


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
        need_role(card.get("column_role"), f"cards.{name}")
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
        if chart_ref is not None:
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
