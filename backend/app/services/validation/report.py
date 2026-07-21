"""
The structured result types every validation stage produces.

A `ValidationReport` is the single shape the upload API returns to the
frontend — on success *and* on failure — so the UI renders one consistent
row-by-row report instead of a generic error toast. Nothing in this
package raises a bare exception to signal "bad data"; a bad file always
comes back as a report with `passed == False` and one issue per problem.

These types are deliberately plain dataclasses (not Pydantic) so the
validation engine has no web-framework dependency; the API layer (Phase
8b) maps them to Pydantic response models at its boundary.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


class Severity(str, enum.Enum):
    """
    ERROR blocks promotion; WARNING is reported but never blocks.

    Intra-file rules (schema, most business rules) are ERROR. Cross-file
    joins are WARNING by design — see PLAN.md Phase 8, stage 4 — because
    they compare two independently-uploaded files and a temporary
    mismatch is expected, not proof the uploaded file is bad.
    """

    ERROR = "error"
    WARNING = "warning"


class Stage(str, enum.Enum):
    """Which pipeline stage produced an issue (see PLAN.md 8a)."""

    SECURITY = "security"
    FILE_INTEGRITY = "file_integrity"
    SCHEMA = "schema"
    BUSINESS = "business"
    CROSS_DATASET = "cross_dataset"


@dataclass
class ValidationIssue:
    """
    One problem found with an uploaded file.

    `row` is the 0-based DataFrame row index the problem is on, or None
    for file-level / column-level problems that aren't tied to one row.
    `column` is None for whole-file problems (e.g. a missing column, a
    security failure). `rule` names the config rule or check that fired,
    so a report row is always traceable back to the contract that
    rejected it.
    """

    stage: Stage
    severity: Severity
    reason: str
    column: str | None = None
    row: int | None = None
    rule: str | None = None
    value: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage.value,
            "severity": self.severity.value,
            "reason": self.reason,
            "column": self.column,
            # +2 so the row number matches what a non-technical admin sees
            # in Excel (1-based, plus the header row). None stays None.
            "excel_row": None if self.row is None else self.row + 2,
            "row_index": self.row,
            "rule": self.rule,
            "value": None if self.value is None else str(self.value),
        }


@dataclass
class ValidationReport:
    """
    The full outcome of validating one uploaded file.

    `passed` is True iff no ERROR-severity issue was raised (warnings do
    not fail a file). `stage_reached` records how far the pipeline got —
    a security failure short-circuits before the schema stage, so the
    report says so rather than implying the schema was checked and clean.
    """

    file_type: str
    schema_version: int | None
    stage_reached: Stage
    rows_total: int | None = None
    rows_checked: int | None = None
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity is Severity.ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity is Severity.WARNING]

    @property
    def passed(self) -> bool:
        return len(self.errors) == 0

    def add(self, issue: ValidationIssue) -> None:
        self.issues.append(issue)

    def extend(self, issues: list[ValidationIssue]) -> None:
        self.issues.extend(issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_type": self.file_type,
            "schema_version": self.schema_version,
            "passed": self.passed,
            "stage_reached": self.stage_reached.value,
            "rows_total": self.rows_total,
            "rows_checked": self.rows_checked,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "issues": [i.to_dict() for i in self.issues],
        }
