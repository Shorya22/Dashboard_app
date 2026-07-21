"""
The validation pipeline orchestrator.

Chains the stages in order — security/integrity → read → schema →
business rules → (optional) cross-dataset — and returns a single
`ValidationReport`. Each stage's failures are collected; a security or
read failure short-circuits (there's nothing safe/meaningful to check
past it), but schema and business stages both run so the admin sees
every problem at once.

This is the one entry point the API layer (Phase 8b) calls. It is
deliberately free of any FastAPI/HTTP types.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

import pandas as pd

from app.services.validation.engine import (
    apply_defaults,
    default_fill_warnings,
    load_config,
    run_business_stage,
    run_schema_stage,
)
from app.services.validation.report import (
    Severity,
    Stage,
    ValidationIssue,
    ValidationReport,
)
from app.services.validation.security import run_security_stage

logger = logging.getLogger(__name__)

# A cross-dataset check: given the just-read DataFrame, return issues
# (warnings, by convention) from comparing it to other active datasets.
CrossDatasetCheck = Callable[[pd.DataFrame], list[ValidationIssue]]


def read_dataframe(path: str | Path, config: dict) -> pd.DataFrame:
    """Read an uploaded file exactly the way its config's `read:` block says."""
    read = config.get("read", {})
    return pd.read_excel(
        path,
        sheet_name=read.get("sheet", 0),
        header=read.get("header", 0),
    )


def validate_file(
    file_type: str,
    path: str | Path,
    *,
    original_filename: str,
    max_bytes: int,
    cross_dataset_checks: list[CrossDatasetCheck] | None = None,
) -> ValidationReport:
    """
    Run the full validation pipeline on one uploaded file.

    `cross_dataset_checks` is injected by the caller (8b) with closures
    that already hold references to the currently-active other datasets;
    the pipeline stays ignorant of what those are. Cross-dataset issues
    are warnings by design and never flip `passed` to False.
    """
    config = load_config(file_type)
    schema_version = config.get("schema_version")
    report = ValidationReport(
        file_type=file_type,
        schema_version=schema_version,
        stage_reached=Stage.SECURITY,
    )

    # Stage 1: security / integrity — short-circuit on failure.
    security_issues = run_security_stage(
        path, original_filename=original_filename, max_bytes=max_bytes
    )
    report.extend(security_issues)
    if security_issues:
        logger.info(
            "validate_file[%s]: rejected at security stage (%d issue(s))",
            file_type,
            len(security_issues),
        )
        return report

    # Stage 2: read the workbook (structure/parse integrity).
    report.stage_reached = Stage.FILE_INTEGRITY
    try:
        df = read_dataframe(path, config)
    except Exception as exc:  # noqa: BLE001 - any parse error is a rejection
        logger.info("validate_file[%s]: failed to read workbook: %s", file_type, exc)
        report.add(
            ValidationIssue(
                stage=Stage.FILE_INTEGRITY,
                severity=Severity.ERROR,
                reason=f"Could not read the expected sheet/format: {exc}",
                rule="unreadable_workbook",
            )
        )
        return report
    report.rows_total = len(df)
    report.rows_checked = len(df)

    # Apply the contract's declared defaults before any check runs, so
    # every stage (and the dashboard, via data_loader) sees the same
    # values. Each substituted cell is reported as a warning first.
    report.extend(default_fill_warnings(df, config))
    df = apply_defaults(df, config)

    # Stage 3: schema (structural + type + allowed values + uniqueness).
    report.stage_reached = Stage.SCHEMA
    report.extend(run_schema_stage(df, config))

    # Stage 4: business rules (cross-field).
    report.stage_reached = Stage.BUSINESS
    report.extend(run_business_stage(df, config))

    # Stage 5: cross-dataset (warnings only; never blocks promotion).
    if cross_dataset_checks:
        report.stage_reached = Stage.CROSS_DATASET
        for check in cross_dataset_checks:
            try:
                report.extend(check(df))
            except Exception as exc:  # noqa: BLE001 - a check bug must not fail the upload
                logger.warning(
                    "validate_file[%s]: cross-dataset check errored: %s",
                    file_type,
                    exc,
                )

    logger.info(
        "validate_file[%s]: done — passed=%s errors=%d warnings=%d",
        file_type,
        report.passed,
        len(report.errors),
        len(report.warnings),
    )
    return report
