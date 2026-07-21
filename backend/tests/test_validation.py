"""
Tests for the Phase 8 config-driven ingestion validation engine.

Fixtures are generated programmatically by corrupting a copy of the real
source file, one rule at a time, rather than committing binary blobs —
so each test states exactly which rule it exercises and stays readable.
The most important test is `test_real_files_pass`: the current live data
MUST validate clean, or we'd be unable to re-upload our own dashboard's data.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.services.validation import (
    available_file_types,
    load_config,
    sha256_bytes,
    sha256_file,
    validate_file,
)
from app.services.validation.report import Severity

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
REAL_FILES = {
    "roster": DATA_DIR / "DEPT - Master Data(Sheet1).xlsx",
    "booking": DATA_DIR / "UTILIZATION DATA SHEET.xlsx",
    "ground_truth": DATA_DIR / "PowerBI_Ready_Utilization_May_2026.xlsx",
}
MAX_BYTES = 25 * 1024 * 1024


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _read_real(file_type: str) -> pd.DataFrame:
    """Read a real source file exactly as its config's read block says."""
    config = load_config(file_type)
    read = config["read"]
    return pd.read_excel(
        REAL_FILES[file_type], sheet_name=read["sheet"], header=read["header"]
    )


def _write(df: pd.DataFrame, path: Path, file_type: str) -> Path:
    """Write a DataFrame to an .xlsx using the sheet name the config expects."""
    sheet = load_config(file_type)["read"]["sheet"]
    sheet_name = sheet if isinstance(sheet, str) else "Sheet1"
    with pd.ExcelWriter(path) as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
    return path


def _validate_df(df: pd.DataFrame, file_type: str, tmp_path: Path):
    path = _write(df, tmp_path / f"{file_type}.xlsx", file_type)
    return validate_file(
        file_type, path, original_filename=path.name, max_bytes=MAX_BYTES
    )


def _rules_fired(report) -> set[str]:
    return {i.rule for i in report.issues}


def _rules_fired_at(report, severity: Severity) -> set[str]:
    return {i.rule for i in report.issues if i.severity is severity}


# --------------------------------------------------------------------------- #
# baseline: the real, live data must pass
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("file_type", list(REAL_FILES))
def test_real_files_pass(file_type):
    report = validate_file(
        file_type,
        REAL_FILES[file_type],
        original_filename=REAL_FILES[file_type].name,
        max_bytes=MAX_BYTES,
    )
    assert report.passed, [i.to_dict() for i in report.errors]
    assert report.errors == []
    assert report.rows_total and report.rows_total > 0


def test_available_file_types():
    assert set(available_file_types()) == {"roster", "booking", "ground_truth"}


# --------------------------------------------------------------------------- #
# roster
# --------------------------------------------------------------------------- #
def test_roster_unknown_grade_is_warning_not_error(tmp_path):
    # Org-structure enums (GRADE/Region/Working Entity) warn on an
    # unrecognized value rather than blocking — a new grade band must not
    # freeze the dashboard.
    df = _read_real("roster")
    df.loc[0, "GRADE"] = "G99"
    report = _validate_df(df, "roster", tmp_path)
    assert report.passed  # warning-only, still promotable
    warned = [i for i in report.warnings if i.column == "GRADE"]
    assert warned and warned[0].rule == "allowed_values"


def test_roster_hexaware_region_and_entity_allowed(tmp_path):
    # Regression: "Hexaware" is a legitimate value for internal staff and
    # must pass cleanly (v2 contract fix).
    df = _read_real("roster")
    df.loc[0, "Region"] = "Hexaware"
    df.loc[0, "Working Entity"] = "Hexaware"
    report = _validate_df(df, "roster", tmp_path)
    assert report.passed, [i.to_dict() for i in report.errors]
    assert not any(
        i.column in {"Region", "Working Entity"} for i in report.issues
    )


def test_roster_unknown_region_is_warning(tmp_path):
    df = _read_real("roster")
    df.loc[0, "Region"] = "MARS"
    report = _validate_df(df, "roster", tmp_path)
    assert report.passed
    assert any(
        i.column == "Region" and i.severity is Severity.WARNING
        for i in report.warnings
    )


def test_roster_total_experience_mismatch(tmp_path):
    df = _read_real("roster")
    df.loc[0, "Total Experience"] = df.loc[0, "Total Experience"] + 5.0
    report = _validate_df(df, "roster", tmp_path)
    assert not report.passed
    assert "total_experience_sum" in _rules_fired(report)
    bad = [i for i in report.errors if i.rule == "total_experience_sum"]
    assert bad[0].row == 0


def test_roster_duplicate_new_emp_id(tmp_path):
    df = _read_real("roster")
    df.loc[1, "NEW_EMP_ID"] = df.loc[0, "NEW_EMP_ID"]
    report = _validate_df(df, "roster", tmp_path)
    assert not report.passed
    assert any(i.column == "NEW_EMP_ID" for i in report.errors)


def test_roster_missing_required_column(tmp_path):
    df = _read_real("roster").drop(columns=["NAME"])
    report = _validate_df(df, "roster", tmp_path)
    assert not report.passed
    assert any(
        (i.column == "NAME") or ("NAME" in (i.reason or "")) for i in report.errors
    )


def test_roster_unknown_column_rejected(tmp_path):
    df = _read_real("roster")
    df["SOME_NEW_COL"] = "x"
    report = _validate_df(df, "roster", tmp_path)
    assert not report.passed
    assert "unknown_column" in _rules_fired(report)


def test_roster_bad_status(tmp_path):
    df = _read_real("roster")
    df.loc[0, "Status"] = "Retired"
    report = _validate_df(df, "roster", tmp_path)
    assert not report.passed
    assert any(i.column == "Status" for i in report.errors)


def test_roster_declaration_pending_is_allowed(tmp_path):
    # Regression for the 2026-07-21 audit finding: "Pending" is a real,
    # legitimate 3rd value and must not be rejected.
    df = _read_real("roster")
    df.loc[0, "Declaration Signed"] = "Pending"
    report = _validate_df(df, "roster", tmp_path)
    assert report.passed, [i.to_dict() for i in report.errors]


def test_roster_doj_dept_tbd_ok_but_garbage_flagged(tmp_path):
    df = _read_real("roster")
    df.loc[0, "DOJ (DEPT)"] = "TBD"           # allowed token
    df.loc[1, "DOJ (DEPT)"] = "not-a-date"    # should fire
    report = _validate_df(df, "roster", tmp_path)
    assert not report.passed
    bad = [i for i in report.errors if i.rule == "doj_dept_date_or_token"]
    assert [i.row for i in bad] == [1]


def test_roster_blank_experience_defaults_to_zero(tmp_path):
    # A new hire whose experience isn't filled in yet must not block the
    # upload: blanks default to 0 (warned, never silent).
    df = _read_real("roster")
    for col in (
        "Hexaware Experience (Years)",
        "Before Hexaware Experience",
        "Total Experience",
    ):
        df.loc[0, col] = None
    report = _validate_df(df, "roster", tmp_path)
    assert report.passed, [i.to_dict() for i in report.errors]
    defaulted = [i for i in report.warnings if i.rule == "defaulted_value"]
    assert len(defaulted) == 3


def test_roster_partial_blank_experience_still_caught_by_sum_rule(tmp_path):
    # Defaulting must not hide a genuine inconsistency: if only one operand
    # is blank and the remaining numbers don't add up, the sum rule fires.
    df = _read_real("roster")
    df.loc[0, "Hexaware Experience (Years)"] = None
    df.loc[0, "Before Hexaware Experience"] = 7.4
    df.loc[0, "Total Experience"] = 0.01  # 0 + 7.4 != 0.01
    report = _validate_df(df, "roster", tmp_path)
    assert not report.passed
    assert "total_experience_sum" in _rules_fired(report)


def test_roster_blank_new_emp_id_still_blocks(tmp_path):
    # NEW_EMP_ID is the one blank that makes numbers wrong (dropped by
    # nunique(dropna=True)), so it must remain a hard error.
    df = _read_real("roster")
    df.loc[0, "NEW_EMP_ID"] = None
    report = _validate_df(df, "roster", tmp_path)
    assert not report.passed
    assert any(i.column == "NEW_EMP_ID" for i in report.errors)


def test_roster_lwd_inactive_is_warning_not_error(tmp_path):
    # Blank LWD on an Inactive row is a warning, never a hard block.
    df = _read_real("roster")
    inactive_idx = df.index[df["Status"] == "Inactive"]
    assert len(inactive_idx) > 0
    df.loc[inactive_idx[0], "LWD"] = None
    report = _validate_df(df, "roster", tmp_path)
    assert report.passed  # warning-only rule doesn't fail the file
    assert "lwd_present_when_inactive" in _rules_fired_at(report, Severity.WARNING)


# --------------------------------------------------------------------------- #
# booking
# --------------------------------------------------------------------------- #
def test_booking_bad_hours_type(tmp_path):
    df = _read_real("booking")
    df.loc[0, "Booked Hours Type"] = "Holiday Hours"
    report = _validate_df(df, "booking", tmp_path)
    assert not report.passed
    assert any(i.column == "Booked Hours Type" for i in report.errors)


def test_booking_negative_hours(tmp_path):
    df = _read_real("booking")
    df.loc[0, "Employee Booked Hours"] = -3.0
    report = _validate_df(df, "booking", tmp_path)
    assert not report.passed
    assert any(i.column == "Employee Booked Hours" for i in report.errors)


def test_booking_month_as_display_string_accepted(tmp_path):
    # Regression: `Month` is an unused display column whose format varies
    # across exports (a real date, or the label "Jun 26"). Neither should
    # be rejected (v2 contract: dtype any).
    df = _read_real("booking")
    df["Month"] = "Jun 26"
    report = _validate_df(df, "booking", tmp_path)
    assert report.passed, [i.to_dict() for i in report.errors]
    assert not any(i.column == "Month" for i in report.issues)


def test_booking_missing_employee_rejected(tmp_path):
    df = _read_real("booking")
    df.loc[0, "Employee"] = None
    report = _validate_df(df, "booking", tmp_path)
    assert not report.passed
    assert any(i.column == "Employee" for i in report.errors)


# --------------------------------------------------------------------------- #
# ground truth
# --------------------------------------------------------------------------- #
def test_ground_truth_weekly_null_ok_but_period_null_fails(tmp_path):
    df = _read_real("ground_truth")
    df.loc[0, "Weekly Utilization %"] = None       # nullable -> ok
    df.loc[1, "Period Total Utilization %"] = None  # non-nullable -> error
    report = _validate_df(df, "ground_truth", tmp_path)
    assert not report.passed
    cols = {i.column for i in report.errors}
    assert "Period Total Utilization %" in cols
    assert "Weekly Utilization %" not in cols


def test_ground_truth_duplicate_employee_week(tmp_path):
    df = _read_real("ground_truth")
    dup = df.iloc[[0]].copy()
    df = pd.concat([df, dup], ignore_index=True)
    report = _validate_df(df, "ground_truth", tmp_path)
    assert not report.passed
    assert "employee_week_unique" in _rules_fired(report)


def test_ground_truth_utilization_out_of_range(tmp_path):
    df = _read_real("ground_truth")
    df.loc[0, "Weekly Utilization %"] = 1.5
    report = _validate_df(df, "ground_truth", tmp_path)
    assert not report.passed
    assert any(i.column == "Weekly Utilization %" for i in report.errors)


# --------------------------------------------------------------------------- #
# security / integrity
# --------------------------------------------------------------------------- #
def test_non_xlsx_extension_rejected(tmp_path):
    p = tmp_path / "roster.csv"
    p.write_text("NEW_EMP_ID,NAME\n1,Foo\n")
    report = validate_file(
        "roster", p, original_filename="roster.csv", max_bytes=MAX_BYTES
    )
    assert not report.passed
    assert "extension_not_allowed" in _rules_fired(report)
    assert report.stage_reached.value == "security"


def test_empty_file_rejected(tmp_path):
    p = tmp_path / "roster.xlsx"
    p.write_bytes(b"")
    report = validate_file(
        "roster", p, original_filename="roster.xlsx", max_bytes=MAX_BYTES
    )
    assert not report.passed
    assert "empty_file" in _rules_fired(report)


def test_corrupt_workbook_rejected(tmp_path):
    p = tmp_path / "roster.xlsx"
    p.write_bytes(b"this is not a real xlsx file, just garbage bytes" * 10)
    report = validate_file(
        "roster", p, original_filename="roster.xlsx", max_bytes=MAX_BYTES
    )
    assert not report.passed
    assert "corrupt_or_encrypted" in _rules_fired(report)


def test_oversize_file_rejected(tmp_path):
    df = _read_real("roster")
    p = _write(df, tmp_path / "roster.xlsx", "roster")
    report = validate_file(
        "roster", p, original_filename="roster.xlsx", max_bytes=1024  # 1 KB cap
    )
    assert not report.passed
    assert "file_too_large" in _rules_fired(report)


# --------------------------------------------------------------------------- #
# fingerprint
# --------------------------------------------------------------------------- #
def test_fingerprint_deterministic_and_matches_bytes(tmp_path):
    p = REAL_FILES["roster"]
    assert sha256_file(p) == sha256_file(p)
    assert sha256_file(p) == sha256_bytes(p.read_bytes())
    assert len(sha256_file(p)) == 64
