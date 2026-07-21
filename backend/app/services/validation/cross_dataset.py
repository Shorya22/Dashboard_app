"""
Cross-dataset validation checks — warnings only, never block promotion.

Roster, booking, and ground-truth are three views of one reality (who /
activity / computed result), so an employee in booking or ground-truth
should exist in the roster. But these are uploaded independently, so a
temporary mismatch (roster updated a week before booking) is expected —
PLAN.md Phase 8 fixes these as WARNINGS. Confirmed current match rates
(2026-07-21): booking→roster 46/46, ground_truth→roster 40/41.

Employee names are free text with inconsistent spacing/middle names, so
matching is token-subset based (same approach the audit used), not exact
string equality.

`data_loader` is imported lazily inside the checks to avoid an import
cycle (data_loader -> validation.storage -> ... ). The pipeline wraps
each check in try/except, so a check that can't load a comparison
dataset degrades to "no warning" rather than failing the upload.
"""

from __future__ import annotations

import re

import pandas as pd

from app.services.validation.pipeline import CrossDatasetCheck
from app.services.validation.report import Severity, Stage, ValidationIssue

# Which column holds the employee name, per dataset.
_EMPLOYEE_COLUMN = {
    "roster": "NAME",
    "booking": "Employee",
    "ground_truth": "Employee",
}


def _norm_tokens(name: object) -> frozenset[str]:
    """Lowercased alphabetic name tokens, for spacing-tolerant matching."""
    if pd.isna(name):
        return frozenset()
    tokens = re.findall(r"[a-z]+", str(name).lower())
    return frozenset(tokens)


def _token_lists(names: pd.Series) -> list[frozenset[str]]:
    out = []
    for n in names.dropna().unique():
        t = _norm_tokens(n)
        if t:
            out.append(t)
    return out


def _has_match(name: object, reference: list[frozenset[str]]) -> bool:
    """Match if the name's tokens are a subset of some reference name's, or vice versa."""
    t = _norm_tokens(name)
    if not t:
        return True  # blank names are a schema-stage concern, not this one
    return any(t <= r or r <= t for r in reference)


def _active_names(file_type: str) -> pd.Series:
    """The employee-name column of the currently active version of a dataset."""
    from app.services import data_loader  # lazy — avoids import cycle

    loaders = {
        "roster": data_loader.get_roster_df,
        "booking": data_loader.get_booking_df,
        "ground_truth": data_loader.get_utilization_ground_truth_df,
    }
    df = loaders[file_type]()
    return df[_EMPLOYEE_COLUMN[file_type]]


def _unmatched_warning_check(
    uploaded_name_col: str, reference_file_type: str, label: str
) -> CrossDatasetCheck:
    """
    Build a check: warn for each distinct name in the uploaded file's
    `uploaded_name_col` that has no match in the active `reference_file_type`.
    """

    def check(df: pd.DataFrame) -> list[ValidationIssue]:
        if uploaded_name_col not in df.columns:
            return []
        reference = _token_lists(_active_names(reference_file_type))
        if not reference:
            return []
        issues: list[ValidationIssue] = []
        for name in sorted(df[uploaded_name_col].dropna().unique(), key=str):
            if not _has_match(name, reference):
                issues.append(
                    ValidationIssue(
                        stage=Stage.CROSS_DATASET,
                        severity=Severity.WARNING,
                        reason=(
                            f"Employee {name!r} has no match in the current "
                            f"{label} — check this isn't a name mismatch"
                        ),
                        column=uploaded_name_col,
                        rule=f"unmatched_in_{reference_file_type}",
                        value=name,
                    )
                )
        return issues

    return check


def checks_for(file_type: str) -> list[CrossDatasetCheck]:
    """
    Cross-dataset checks to run when uploading `file_type`.

    - booking / ground_truth upload: warn for employees absent from the
      active roster (the master list of who exists).
    - roster upload: warn for active booking/ground_truth employees who
      would no longer have a roster row after this upload.
    """
    if file_type == "booking":
        return [_unmatched_warning_check("Employee", "roster", "roster")]
    if file_type == "ground_truth":
        return [_unmatched_warning_check("Employee", "roster", "roster")]
    if file_type == "roster":
        return [
            _reverse_unmatched_check("booking", "booking data"),
            _reverse_unmatched_check("ground_truth", "utilization ground-truth data"),
        ]
    return []


def _reverse_unmatched_check(
    active_file_type: str, label: str
) -> CrossDatasetCheck:
    """
    For a roster upload: warn for each employee in the active
    `active_file_type` who has no match in the *uploaded roster* (df).
    """

    def check(df: pd.DataFrame) -> list[ValidationIssue]:
        roster_names = "NAME"
        if roster_names not in df.columns:
            return []
        reference = _token_lists(df[roster_names])
        if not reference:
            return []
        try:
            active = _active_names(active_file_type)
        except Exception:  # noqa: BLE001 - missing comparison data => skip
            return []
        issues: list[ValidationIssue] = []
        for name in sorted(active.dropna().unique(), key=str):
            if not _has_match(name, reference):
                issues.append(
                    ValidationIssue(
                        stage=Stage.CROSS_DATASET,
                        severity=Severity.WARNING,
                        reason=(
                            f"Employee {name!r} appears in the current {label} "
                            f"but is not in this roster upload"
                        ),
                        column=roster_names,
                        rule=f"missing_from_roster_but_in_{active_file_type}",
                        value=name,
                    )
                )
        return issues

    return check
