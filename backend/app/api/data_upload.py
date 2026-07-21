"""
Admin-only data upload / ingestion endpoints (Phase 8b).

Thin per api-conventions: each route saves the upload to a quarantine
temp file, delegates to `services/validation/service.py`, and maps the
result to a typed response model. No validation or storage logic here.

Every mutating/reading route is gated on the `admin` role (reusing the
Phase-3 role field). A validation failure returns HTTP 422 with the full
structured report so the frontend can render it row-by-row; a security
rejection also returns 422. Nothing here ever raises a bare 500 for bad
*data* — only for genuinely unexpected server errors.
"""

from __future__ import annotations

import io
import logging
import tempfile
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse

from app.core.security import require_role
from app.db.models import User
from app.models.data_upload import (
    AuditEntryModel,
    DatasetStatusListModel,
    DatasetStatusModel,
    HistoryModel,
    RollbackResultModel,
    SchemaColumnModel,
    SchemaModel,
    SchemaRuleModel,
    UploadResultModel,
    ValidationReportModel,
    VersionModel,
)
from app.services.validation import storage
from app.services.validation.engine import available_file_types, load_config
from app.services.validation.service import (
    UnknownFileType,
    process_upload,
    validate_only,
)
from app.services.validation.service import rollback as rollback_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data", tags=["data-upload"])

_XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# Admin-only dependency, reused on every route in this module.
require_admin = require_role("admin")


def _ensure_known(file_type: str) -> None:
    if file_type not in available_file_types():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Unknown dataset {file_type!r}. Valid: "
                f"{', '.join(available_file_types())}"
            ),
        )


def _save_upload_to_temp(upload: UploadFile) -> Path:
    """Stream an UploadFile to a quarantine temp file, returning its path."""
    suffix = Path(upload.filename or "upload").suffix or ".bin"
    fd, tmp_name = tempfile.mkstemp(prefix="upload_", suffix=suffix)
    tmp_path = Path(tmp_name)
    try:
        with open(fd, "wb") as out:
            while True:
                chunk = upload.file.read(1 << 20)
                if not chunk:
                    break
                out.write(chunk)
    finally:
        upload.file.close()
    return tmp_path


@router.post("/validate/{file_type}", response_model=ValidationReportModel)
def validate_upload(
    file_type: str,
    file: UploadFile = File(...),
    user: User = Depends(require_admin),
) -> ValidationReportModel:
    """Dry run: validate an upload and return the report; store nothing."""
    _ensure_known(file_type)
    tmp = _save_upload_to_temp(file)
    try:
        report = validate_only(
            file_type, tmp, original_filename=file.filename or "upload.xlsx"
        )
    finally:
        tmp.unlink(missing_ok=True)
    return ValidationReportModel(**report.to_dict())


@router.post("/upload/{file_type}", response_model=UploadResultModel)
def upload_dataset(
    file_type: str,
    file: UploadFile = File(...),
    user: User = Depends(require_admin),
) -> UploadResultModel:
    """
    Validate and, on a clean pass, promote a new immutable version and
    refresh the live dashboard cache. Returns 422 (with the full report)
    if validation fails, so nothing reaches the active dataset.
    """
    _ensure_known(file_type)
    tmp = _save_upload_to_temp(file)
    try:
        result = process_upload(
            file_type,
            tmp,
            original_filename=file.filename or "upload.xlsx",
            uploaded_by=user.email,
        )
    except UnknownFileType as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        tmp.unlink(missing_ok=True)

    report_model = ValidationReportModel(**result.report.to_dict())
    messages = {
        "promoted": f"Uploaded and promoted as version {result.version}.",
        "duplicate": (
            f"This exact file is already active as version {result.version}; "
            "no new version created."
        ),
        "rejected": (
            f"Rejected: {len(result.report.errors)} validation error(s). "
            "The live data was not changed."
        ),
    }
    payload = UploadResultModel(
        status=result.status,
        version=result.version,
        active_version=result.active_version,
        message=messages[result.status],
        report=report_model,
    )
    if result.status == "rejected":
        # 422 carries the structured report as the response body.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=payload.model_dump(),
        )
    return payload


@router.post("/rollback/{file_type}", response_model=RollbackResultModel)
def rollback_dataset(
    file_type: str,
    user: User = Depends(require_admin),
) -> RollbackResultModel:
    """Restore the previous active version and refresh the live cache."""
    _ensure_known(file_type)
    try:
        target = rollback_service(file_type, user=user.email)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return RollbackResultModel(
        file_type=file_type,
        active_version=target,
        message=f"Rolled back to version {target}.",
    )


@router.get("/history/{file_type}", response_model=HistoryModel)
def dataset_history(
    file_type: str,
    user: User = Depends(require_admin),
) -> HistoryModel:
    """Full version + audit history for a dataset."""
    _ensure_known(file_type)
    manifest = storage.read_manifest(file_type)
    active = manifest.get("active_version")
    versions = [
        VersionModel(**{**v, "is_active": v["version"] == active})
        for v in manifest.get("versions", [])
    ]
    audit = [AuditEntryModel(**a) for a in manifest.get("audit_log", [])]
    return HistoryModel(
        file_type=file_type,
        active_version=active,
        versions=versions,
        audit_log=audit,
    )


@router.get("/schema/{file_type}", response_model=SchemaModel)
def dataset_schema(
    file_type: str,
    user: User = Depends(require_admin),
) -> SchemaModel:
    """
    The dataset's contract, serialized from its YAML config — the same
    file the validator uses, so the UI template/checklist can never
    drift from what's actually enforced.
    """
    _ensure_known(file_type)
    config = load_config(file_type)
    columns = [
        SchemaColumnModel(
            name=c["name"],
            dtype=c["dtype"],
            required=c.get("required", True),
            nullable=c.get("nullable", True),
            unique=c.get("unique", False),
            allowed_values=c.get("allowed_values"),
            min=c.get("min"),
            max=c.get("max"),
        )
        for c in config["columns"]
    ]
    rules = [
        SchemaRuleModel(
            name=r["name"],
            type=r["type"],
            severity=r.get("severity", "error"),
            reason=r["reason"],
        )
        for r in config.get("business_rules", [])
    ]
    return SchemaModel(
        file_type=file_type,
        schema_version=config["schema_version"],
        display_name=config.get("display_name", file_type),
        source_file=config.get("source_file"),
        allow_unknown_columns=config.get("allow_unknown_columns", False),
        columns=columns,
        business_rules=rules,
    )


@router.get("/status", response_model=DatasetStatusListModel)
def datasets_status(
    user: User = Depends(require_admin),
) -> DatasetStatusListModel:
    """Active version + source (uploaded vs bundled default) for every dataset."""
    out: list[DatasetStatusModel] = []
    for file_type in available_file_types():
        config = load_config(file_type)
        manifest = storage.read_manifest(file_type)
        active = manifest.get("active_version")
        active_entry = next(
            (v for v in manifest.get("versions", []) if v["version"] == active),
            None,
        )
        out.append(
            DatasetStatusModel(
                file_type=file_type,
                display_name=config.get("display_name", file_type),
                schema_version=config["schema_version"],
                active_version=active,
                source="uploaded" if active is not None else "default",
                uploaded_at=active_entry["uploaded_at"] if active_entry else None,
                uploaded_by=active_entry["uploaded_by"] if active_entry else None,
                rows_total=active_entry["rows_total"] if active_entry else None,
            )
        )
    return DatasetStatusListModel(datasets=out)


@router.get("/template/{file_type}")
def download_template(
    file_type: str,
    user: User = Depends(require_admin),
) -> StreamingResponse:
    """A blank .xlsx with exactly the expected columns, built from the config."""
    _ensure_known(file_type)
    config = load_config(file_type)
    columns = [c["name"] for c in config["columns"]]
    buffer = io.BytesIO()
    sheet = config["read"].get("sheet")
    sheet_name = sheet if isinstance(sheet, str) else "Sheet1"
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        pd.DataFrame(columns=columns).to_excel(
            writer, sheet_name=sheet_name, index=False
        )
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type=_XLSX_MEDIA,
        headers={
            "Content-Disposition": f'attachment; filename="{file_type}_template.xlsx"'
        },
    )


@router.get("/report/{file_type}/{version}")
def download_report(
    file_type: str,
    version: int,
    user: User = Depends(require_admin),
) -> StreamingResponse:
    """Download a stored version's validation report as an .xlsx."""
    _ensure_known(file_type)
    path = storage.report_path(file_type, version)
    if not path.exists():
        raise HTTPException(
            status_code=404, detail=f"No stored report for {file_type} v{version}"
        )
    import json

    with path.open("r", encoding="utf-8") as fh:
        report = json.load(fh)
    issues = report.get("issues", [])
    df = (
        pd.DataFrame(issues)
        if issues
        else pd.DataFrame(
            columns=["stage", "severity", "column", "excel_row", "rule", "reason", "value"]
        )
    )
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="validation_report", index=False)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type=_XLSX_MEDIA,
        headers={
            "Content-Disposition": (
                f'attachment; filename="{file_type}_v{version}_report.xlsx"'
            )
        },
    )
