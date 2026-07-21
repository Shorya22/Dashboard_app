"""Response models for the Phase 8 data-upload / ingestion endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ValidationIssueModel(BaseModel):
    stage: str = Field(..., description="Pipeline stage that raised the issue")
    severity: str = Field(..., description="'error' (blocks) or 'warning'")
    reason: str
    column: str | None = None
    excel_row: int | None = Field(
        None, description="1-based row as seen in Excel (incl. header), or null"
    )
    row_index: int | None = Field(None, description="0-based DataFrame row, or null")
    rule: str | None = None
    value: str | None = None


class ValidationReportModel(BaseModel):
    file_type: str
    schema_version: int | None
    passed: bool
    stage_reached: str
    rows_total: int | None = None
    rows_checked: int | None = None
    error_count: int
    warning_count: int
    issues: list[ValidationIssueModel]


class UploadResultModel(BaseModel):
    status: str = Field(..., description="'promoted', 'rejected', or 'duplicate'")
    version: int | None = Field(None, description="New/active version, if any")
    active_version: int | None = None
    message: str
    report: ValidationReportModel


class RollbackResultModel(BaseModel):
    file_type: str
    active_version: int
    message: str


class VersionModel(BaseModel):
    version: int
    sha256: str
    schema_version: int | None = None
    filename: str
    original_filename: str
    uploaded_by: str
    uploaded_at: str
    rows_total: int | None = None
    error_count: int = 0
    warning_count: int = 0
    is_active: bool


class AuditEntryModel(BaseModel):
    action: str
    timestamp: str
    user: str
    version: int | None = None
    detail: str


class HistoryModel(BaseModel):
    file_type: str
    active_version: int | None = None
    versions: list[VersionModel]
    audit_log: list[AuditEntryModel]


class SchemaColumnModel(BaseModel):
    name: str
    dtype: str
    required: bool
    nullable: bool
    unique: bool = False
    allowed_values: list[Any] | None = None
    min: float | None = None
    max: float | None = None


class SchemaRuleModel(BaseModel):
    name: str
    type: str
    severity: str
    reason: str


class SchemaModel(BaseModel):
    file_type: str
    schema_version: int
    display_name: str
    source_file: str | None = None
    allow_unknown_columns: bool = False
    columns: list[SchemaColumnModel]
    business_rules: list[SchemaRuleModel]


class DatasetStatusModel(BaseModel):
    file_type: str
    display_name: str
    schema_version: int
    active_version: int | None = None
    source: str = Field(..., description="'uploaded' or 'default' (bundled file)")
    uploaded_at: str | None = None
    uploaded_by: str | None = None
    rows_total: int | None = None


class DatasetStatusListModel(BaseModel):
    datasets: list[DatasetStatusModel]
