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

CONFIG_PATH = Path(__file__).resolve().parent / "configs" / "roster_metrics.yaml"


@functools.lru_cache(maxsize=1)
def load_metric_config() -> dict:
    """Load and cache the roster metric-semantics config."""
    with CONFIG_PATH.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def status_column() -> str:
    return load_metric_config()["status"]["column"]


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
    return load_metric_config()["seniority"]["column"]


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
