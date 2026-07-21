"""
File-level security + integrity checks — the first pipeline stage.

These run BEFORE pandas ever opens the workbook, so a hostile or
malformed file is rejected without handing it to a parser. Any ERROR
here short-circuits the pipeline (no schema/business checks run on a
file we won't safely open).

Checks: extension allow-list, size cap (config-driven, not hardcoded),
real ZIP/OOXML integrity (an encrypted .xlsx is an OLE2 compound file,
not a ZIP — so is_zipfile is False), and embedded VBA macros. Macro
workbooks (.xlsm) are rejected both by extension and by detecting
vbaProject.bin inside the archive.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from app.services.validation.report import Severity, Stage, ValidationIssue

ALLOWED_EXTENSIONS = {".xlsx"}
# Parts inside the OOXML zip that indicate executable content.
_MACRO_PARTS = ("vbaproject.bin",)


def _err(reason: str, rule: str) -> ValidationIssue:
    return ValidationIssue(
        stage=Stage.SECURITY,
        severity=Severity.ERROR,
        reason=reason,
        rule=rule,
    )


def run_security_stage(
    path: str | Path, *, original_filename: str, max_bytes: int
) -> list[ValidationIssue]:
    """
    Validate an uploaded file at the byte level. Returns a list of
    ERROR issues; an empty list means the file is safe to open. Stops at
    the first failure category (each check gates the next).
    """
    path = Path(path)
    name = original_filename or path.name

    # 1. Extension allow-list (checked against the ORIGINAL upload name,
    #    not the quarantine temp name).
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return [
            _err(
                f"File type {ext or '(none)'!r} is not allowed; only "
                f"{', '.join(sorted(ALLOWED_EXTENSIONS))} is accepted",
                "extension_not_allowed",
            )
        ]

    # 2. Size cap (config-driven).
    size = path.stat().st_size
    if size == 0:
        return [_err("File is empty", "empty_file")]
    if size > max_bytes:
        return [
            _err(
                f"File is {size:,} bytes, over the {max_bytes:,}-byte limit",
                "file_too_large",
            )
        ]

    # 3. Real OOXML/zip integrity. A valid .xlsx is a ZIP; a corrupt file
    #    or a password-encrypted workbook (OLE2 compound file) is not.
    if not zipfile.is_zipfile(path):
        return [
            _err(
                "File is not a readable .xlsx — it may be corrupt, "
                "password-protected, or encrypted",
                "corrupt_or_encrypted",
            )
        ]

    # 4. Macro / executable content.
    try:
        with zipfile.ZipFile(path) as zf:
            bad = zf.testzip()
            if bad is not None:
                return [_err(f"Corrupt entry in workbook: {bad}", "corrupt_zip_entry")]
            names_lower = [n.lower() for n in zf.namelist()]
    except zipfile.BadZipFile:
        return [_err("File is not a readable .xlsx (bad zip)", "bad_zip")]

    if any(part in n for n in names_lower for part in _MACRO_PARTS):
        return [
            _err(
                "Workbook contains embedded macros (VBA) and was rejected",
                "macros_present",
            )
        ]

    return []
