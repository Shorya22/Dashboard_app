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

# Frozen, known-clean copies used as the baseline for the mutation tests
# below (each deliberately breaks ONE thing and asserts only that thing is
# reported). They must not read the live files: those are business data
# that legitimately changes, so a new upload with its own blanks would
# make these tests fail for reasons unrelated to what they check.
# `test_real_files_pass` deliberately still reads the LIVE files.
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
SNAPSHOTS = {
    "roster": FIXTURES_DIR / "roster_snapshot.xlsx",
    "booking": FIXTURES_DIR / "booking_snapshot.xlsx",
    "ground_truth": FIXTURES_DIR / "ground_truth_snapshot.xlsx",
}


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _read_real(file_type: str) -> pd.DataFrame:
    """Read the frozen clean snapshot exactly as its config's read block says."""
    config = load_config(file_type)
    read = config["read"]
    return pd.read_excel(
        SNAPSHOTS[file_type], sheet_name=read["sheet"], header=read["header"]
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
# LIGHT MODE (schema v7): no `allowed_values` literals anywhere, so any
# value in a classification column is accepted. These columns legitimately
# gain values over time (a new grade band, region, entity, status), and a
# fixed list would freeze the dashboard the day one appears. Structural
# checks (below) are what still catch a genuinely wrong file.
@pytest.mark.parametrize(
    "column,value",
    [
        ("GRADE", "G99"),
        ("Region", "MARS"),
        ("Region", "Hexaware"),          # legitimate internal-staff value
        ("Working Entity", "Hexaware"),
        ("Status", "Retired"),
        ("Type", "Contractor"),
        ("Declaration Signed", "Pending"),
        ("Seniorirty Level", "Brand New Band"),
    ],
)
def test_roster_any_classification_value_is_accepted(column, value, tmp_path):
    df = _read_real("roster")
    df.loc[0, column] = value
    report = _validate_df(df, "roster", tmp_path)
    assert report.passed, [i.to_dict() for i in report.errors]
    assert not any(i.column == column for i in report.issues)


def test_roster_total_experience_taken_as_given(tmp_path):
    # v5 (business owner's decision): experience values are taken exactly
    # as supplied — Total Experience is never reconciled against
    # Hexaware + Before, since the app only reads it and never recomputes it.
    df = _read_real("roster")
    df.loc[0, "Total Experience"] = df.loc[0, "Total Experience"] + 5.0
    report = _validate_df(df, "roster", tmp_path)
    assert report.passed, [i.to_dict() for i in report.errors]
    assert "total_experience_sum" not in _rules_fired(report)


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


@pytest.mark.parametrize(
    "heading",
    [
        "Client",                    # canonical (source now exports this)
        "Client as on June 2026",    # older export
        "Client as on July 2026",    # a future month, unseen by anyone
        "Client as on Q3 2027",
    ],
)
def test_client_column_heading_may_carry_any_period(heading, tmp_path):
    """
    The client heading used to carry the reporting period, so it changed
    every export and would have failed the required-column check each
    month. Any such heading is now matched by pattern and renamed to the
    canonical "Client", so a new period's file uploads with no config or
    code change.
    """
    df = _read_real("roster").rename(columns={"Client": heading})
    report = _validate_df(df, "roster", tmp_path)
    assert report.passed, [i.to_dict() for i in report.errors]
    # ...and it must not be reported as an unexpected/extra column either
    assert not any(i.rule == "unknown_column" for i in report.issues)


def test_roster_extra_column_is_warning_not_error(tmp_path):
    # Light mode: an added column is reported so it's visible, but a file
    # that gained a column is not rejected.
    df = _read_real("roster")
    df["SOME_NEW_COL"] = "x"
    report = _validate_df(df, "roster", tmp_path)
    assert report.passed, [i.to_dict() for i in report.errors]
    assert "unknown_column" in _rules_fired(report)


def test_roster_date_columns_accept_any_format(tmp_path):
    # Date columns are untyped in light mode — they arrive as DD-Mon-YY
    # text or real dates depending on the export, and the app parses them
    # itself with coercion.
    df = _read_real("roster")
    df.loc[0, "DOJ (DEPT)"] = "TBD"
    df.loc[1, "DOJ (DEPT)"] = "not-a-date"
    report = _validate_df(df, "roster", tmp_path)
    assert report.passed, [i.to_dict() for i in report.errors]


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


def test_roster_partial_blank_experience_accepted_as_given(tmp_path):
    # A partly-filled experience row (blank operand + a Total that doesn't
    # match the parts) is accepted: the blank defaults to 0 and the stated
    # Total is kept verbatim. No reconciliation is performed.
    df = _read_real("roster")
    df.loc[0, "Hexaware Experience (Years)"] = None
    df.loc[0, "Before Hexaware Experience"] = 7.4
    df.loc[0, "Total Experience"] = 0.01
    report = _validate_df(df, "roster", tmp_path)
    assert report.passed, [i.to_dict() for i in report.errors]


def test_roster_blank_new_emp_id_becomes_numbered_tbd_marker(tmp_path):
    # v6: a blank id no longer blocks — it becomes "NEW_EMP_ID TBD n".
    df = _read_real("roster")
    df.loc[0, "NEW_EMP_ID"] = None
    df.loc[1, "NEW_EMP_ID"] = None
    report = _validate_df(df, "roster", tmp_path)
    assert report.passed, [i.to_dict() for i in report.errors]
    defaulted = [
        i
        for i in report.warnings
        if i.rule == "defaulted_value" and i.column == "NEW_EMP_ID"
    ]
    # Distinct markers, NOT one shared value — see below for why.
    assert [i.value for i in defaulted] == ["NEW_EMP_ID TBD 1", "NEW_EMP_ID TBD 2"]


def test_blank_ids_do_not_undercount_headcount(tmp_path):
    """
    The headcount measures are `NEW_EMP_ID.nunique()`, so two blank ids
    filled with one shared marker would collapse into a single distinct
    value and silently under-count. Numbering keeps them separate.
    """
    from app.services import roster_metrics
    from app.services.validation.engine import apply_dataset_defaults

    df = _read_real("roster")
    df.loc[0, "NEW_EMP_ID"] = None
    df.loc[1, "NEW_EMP_ID"] = None
    filled = apply_dataset_defaults(df, "roster")
    assert roster_metrics.get_total_employees(filled) == len(df)


def test_existing_ids_render_without_float_artifacts(tmp_path):
    # A single blank makes pandas read the id column as float64; real ids
    # must not end up rendered as "2000194634.0".
    from app.services.validation.engine import apply_dataset_defaults

    df = _read_real("roster")
    df.loc[0, "NEW_EMP_ID"] = None
    filled = apply_dataset_defaults(df, "roster")
    assert not any(str(v).endswith(".0") for v in filled["NEW_EMP_ID"])


def test_roster_blank_lwd_on_inactive_is_accepted(tmp_path):
    # Light mode: no cross-field rules, so Status/LWD are not reconciled.
    df = _read_real("roster")
    inactive_idx = df.index[df["Status"] == "Inactive"]
    assert len(inactive_idx) > 0
    df.loc[inactive_idx[0], "LWD"] = None
    report = _validate_df(df, "roster", tmp_path)
    assert report.passed, [i.to_dict() for i in report.errors]


# --------------------------------------------------------------------------- #
# booking
# --------------------------------------------------------------------------- #
def test_booking_any_hours_type_accepted(tmp_path):
    # No fixed list — a new booking category must not block the upload.
    df = _read_real("booking")
    df.loc[0, "Booked Hours Type"] = "Holiday Hours"
    report = _validate_df(df, "booking", tmp_path)
    assert report.passed, [i.to_dict() for i in report.errors]


def test_booking_hours_stay_numeric(tmp_path):
    # The one thing still enforced on hours: it must be a number, because
    # every utilization metric sums it. Text here would break the charts.
    df = _read_real("booking")
    df["Employee Booked Hours"] = "not a number"
    report = _validate_df(df, "booking", tmp_path)
    assert not report.passed
    assert any(i.column == "Employee Booked Hours" for i in report.errors)


def test_booking_month_as_display_string_accepted(tmp_path):
    # Regression: `Month` is an unused display column whose format varies
    # across exports (a real date, or the label "Jun 26"). Neither should
    # be rejected.
    df = _read_real("booking")
    df["Month"] = "Jun 26"
    report = _validate_df(df, "booking", tmp_path)
    assert report.passed, [i.to_dict() for i in report.errors]
    assert not any(i.column == "Month" for i in report.issues)


def test_booking_missing_employee_is_warning(tmp_path):
    # A row with no Employee is dropped downstream anyway; surfaced as a
    # warning so it's visible, but it no longer blocks.
    df = _read_real("booking")
    df.loc[0, "Employee"] = None
    report = _validate_df(df, "booking", tmp_path)
    assert report.passed, [i.to_dict() for i in report.errors]
    assert "empty_optional_value" in _rules_fired_at(report, Severity.WARNING)


# --------------------------------------------------------------------------- #
# ground truth
# --------------------------------------------------------------------------- #
def test_ground_truth_blank_utilization_accepted(tmp_path):
    # Both utilization columns are nullable in light mode. Weekly blanks are
    # meaningful (no booking-based rate that week) and must NOT be defaulted
    # to 0, which would drag the average down with a fake zero.
    df = _read_real("ground_truth")
    df.loc[0, "Weekly Utilization %"] = None
    df.loc[1, "Period Total Utilization %"] = None
    report = _validate_df(df, "ground_truth", tmp_path)
    assert report.passed, [i.to_dict() for i in report.errors]


def test_ground_truth_utilization_above_100_pct_accepted(tmp_path):
    # No upper bound: overtime can legitimately exceed 100%.
    df = _read_real("ground_truth")
    df.loc[0, "Weekly Utilization %"] = 1.5
    report = _validate_df(df, "ground_truth", tmp_path)
    assert report.passed, [i.to_dict() for i in report.errors]


def test_ground_truth_utilization_stays_numeric(tmp_path):
    df = _read_real("ground_truth")
    df["Weekly Utilization %"] = "high"
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
