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
        return yaml.safe_load(fh)


# --- booking ------------------------------------------------------------- #
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


def filters() -> dict[str, dict]:
    """The declared page filters, keyed by filter name."""
    return load_metric_config().get("filters", {})


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
