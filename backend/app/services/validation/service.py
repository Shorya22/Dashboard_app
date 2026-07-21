"""
Ingestion orchestration — the one function the upload API calls.

Ties the pieces together: run the full validation pipeline (with
cross-dataset warning checks), and on a clean pass either promote a new
immutable version and refresh the live cache, or short-circuit as a
no-op when the identical file is already active (fingerprint idempotency).
A failing file is recorded in the audit log and never promoted.

Kept free of FastAPI types so it stays unit-testable; the route is a
thin wrapper over `process_upload` / `validate_only`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings
from app.services.validation import cross_dataset, storage
from app.services.validation.engine import available_file_types
from app.services.validation.fingerprint import sha256_file
from app.services.validation.pipeline import validate_file
from app.services.validation.report import ValidationReport

logger = logging.getLogger(__name__)


class UnknownFileType(ValueError):
    """Raised for a file_type with no validation config."""


def ensure_known(file_type: str) -> None:
    if file_type not in available_file_types():
        raise UnknownFileType(
            f"Unknown file_type {file_type!r}; valid: {available_file_types()}"
        )


def _reload_active(file_type: str) -> None:
    """Refresh the live in-memory cache so the dashboard sees the new version."""
    from app.services import data_loader  # lazy — avoids import cycle

    {
        "roster": data_loader.reload_roster,
        "booking": data_loader.reload_booking_data,
        "ground_truth": data_loader.reload_utilization_ground_truth,
    }[file_type]()


def validate_only(
    file_type: str, tmp_path: str | Path, *, original_filename: str
) -> ValidationReport:
    """Dry run: full validation, nothing stored or promoted."""
    ensure_known(file_type)
    return validate_file(
        file_type,
        tmp_path,
        original_filename=original_filename,
        max_bytes=settings.max_upload_bytes,
        cross_dataset_checks=cross_dataset.checks_for(file_type),
    )


@dataclass
class UploadResult:
    status: str  # "promoted" | "rejected" | "duplicate"
    report: ValidationReport
    version: int | None = None
    active_version: int | None = None


def process_upload(
    file_type: str,
    tmp_path: str | Path,
    *,
    original_filename: str,
    uploaded_by: str,
) -> UploadResult:
    """
    Validate, then (on pass) fingerprint-dedup or promote + reload.

    Never touches the active dataset until validation passes.
    """
    ensure_known(file_type)
    report = validate_only(file_type, tmp_path, original_filename=original_filename)

    if not report.passed:
        storage.record_rejection(
            file_type,
            user=uploaded_by,
            original_filename=original_filename,
            error_count=len(report.errors),
        )
        return UploadResult(status="rejected", report=report)

    sha = sha256_file(tmp_path)
    existing = storage.find_version_by_hash(file_type, sha)
    if existing is not None and existing == storage.active_version(file_type):
        logger.info(
            "process_upload[%s]: identical file already active as v%d — no-op",
            file_type,
            existing,
        )
        return UploadResult(
            status="duplicate",
            report=report,
            version=existing,
            active_version=existing,
        )

    entry = storage.store_and_promote(
        file_type,
        tmp_path,
        sha256=sha,
        schema_version=report.schema_version,
        original_filename=original_filename,
        uploaded_by=uploaded_by,
        report=report.to_dict(),
    )
    _reload_active(file_type)
    return UploadResult(
        status="promoted",
        report=report,
        version=entry["version"],
        active_version=entry["version"],
    )


def rollback(file_type: str, *, user: str) -> int:
    """Roll back to the previous version and refresh the live cache."""
    ensure_known(file_type)
    target = storage.rollback(file_type, user=user)
    _reload_active(file_type)
    return target
