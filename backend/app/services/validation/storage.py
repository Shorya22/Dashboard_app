"""
Immutable, versioned storage for uploaded datasets + rollback.

Every successful upload for a file type is written once as
`<base>/<file_type>/v<N>.xlsx` and never overwritten — so history is
purely "which version is active", tracked by a per-file-type
`manifest.json`. Rolling back just moves the active pointer to an
earlier version; the files themselves are immutable.

`resolved_path(file_type)` is the single seam the rest of the app reads
through: it returns the active uploaded version if one exists, otherwise
the bundled default source file — so the app works unchanged before any
upload has ever happened.

No database is involved (matching the current app: only `users` is in a
DB). A process-level lock guards the read-modify-write of each manifest;
manifest writes are atomic (temp file + os.replace).
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import shutil
import threading
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.services.booking_metrics import DEFAULT_BOOKING_PATH
from app.services.roster_metrics import DEFAULT_ROSTER_PATH
from app.services.utilization_metrics import DEFAULT_GROUND_TRUTH_PATH

logger = logging.getLogger(__name__)

# The bundled source file used before any upload exists, per file type.
_DEFAULT_PATHS: dict[str, Path] = {
    "roster": DEFAULT_ROSTER_PATH,
    "booking": DEFAULT_BOOKING_PATH,
    "ground_truth": DEFAULT_GROUND_TRUTH_PATH,
}

_lock = threading.Lock()


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _base_dir() -> Path:
    """Storage root, read from settings each call so tests can override it."""
    return Path(settings.upload_storage_dir)


def _dataset_dir(file_type: str) -> Path:
    return _base_dir() / file_type


def _manifest_path(file_type: str) -> Path:
    return _dataset_dir(file_type) / "manifest.json"


def _empty_manifest(file_type: str) -> dict[str, Any]:
    return {
        "file_type": file_type,
        "active_version": None,
        "versions": [],
        "audit_log": [],
    }


def read_manifest(file_type: str) -> dict[str, Any]:
    """Return the manifest for a file type, or an empty one if none yet."""
    path = _manifest_path(file_type)
    if not path.exists():
        return _empty_manifest(file_type)
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_manifest(file_type: str, manifest: dict[str, Any]) -> None:
    """Atomically write a manifest (temp file + os.replace)."""
    directory = _dataset_dir(file_type)
    directory.mkdir(parents=True, exist_ok=True)
    tmp = directory / f".manifest.{os.getpid()}.tmp"
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    os.replace(tmp, _manifest_path(file_type))


def resolved_path(file_type: str) -> Path:
    """
    The file the app should currently read for this dataset: the active
    uploaded version if one exists, otherwise the bundled default.
    """
    manifest = read_manifest(file_type)
    active = manifest.get("active_version")
    if active is not None:
        return _dataset_dir(file_type) / f"v{active}.xlsx"
    if file_type not in _DEFAULT_PATHS:
        raise KeyError(f"Unknown file_type {file_type!r}")
    return _DEFAULT_PATHS[file_type]


def _version_entry(manifest: dict[str, Any], version: int) -> dict[str, Any] | None:
    return next((v for v in manifest["versions"] if v["version"] == version), None)


def active_version(file_type: str) -> int | None:
    return read_manifest(file_type).get("active_version")


def find_version_by_hash(file_type: str, sha256: str) -> int | None:
    """Return the version whose stored file has this hash, if any (idempotency)."""
    for v in read_manifest(file_type)["versions"]:
        if v.get("sha256") == sha256:
            return v["version"]
    return None


def report_path(file_type: str, version: int) -> Path:
    return _dataset_dir(file_type) / f"v{version}.report.json"


def store_and_promote(
    file_type: str,
    src_path: str | Path,
    *,
    sha256: str,
    schema_version: int | None,
    original_filename: str,
    uploaded_by: str,
    report: dict[str, Any],
) -> dict[str, Any]:
    """
    Store `src_path` as the next immutable version and make it active.

    Returns the new version entry. The prior active version's file is
    left untouched (immutable) — only the active pointer moves.
    """
    with _lock:
        manifest = read_manifest(file_type)
        versions = manifest["versions"]
        next_version = (max((v["version"] for v in versions), default=0)) + 1

        directory = _dataset_dir(file_type)
        directory.mkdir(parents=True, exist_ok=True)
        dest = directory / f"v{next_version}.xlsx"
        shutil.copyfile(src_path, dest)

        entry = {
            "version": next_version,
            "sha256": sha256,
            "schema_version": schema_version,
            "filename": dest.name,
            "original_filename": original_filename,
            "uploaded_by": uploaded_by,
            "uploaded_at": _now(),
            "rows_total": report.get("rows_total"),
            "error_count": report.get("error_count", 0),
            "warning_count": report.get("warning_count", 0),
        }
        versions.append(entry)
        previous_active = manifest.get("active_version")
        manifest["active_version"] = next_version
        manifest["audit_log"].append(
            {
                "action": "uploaded",
                "timestamp": entry["uploaded_at"],
                "user": uploaded_by,
                "version": next_version,
                "detail": (
                    f"promoted v{next_version} "
                    f"(replaced v{previous_active})"
                    if previous_active
                    else f"promoted v{next_version} (first upload)"
                ),
            }
        )

        # Store the full validation report next to the version file so it
        # can be downloaded later (audit trail / hand to whoever prepared
        # the source file).
        with report_path(file_type, next_version).open("w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)

        _write_manifest(file_type, manifest)
        logger.info(
            "store_and_promote[%s]: stored+promoted v%d by %s",
            file_type,
            next_version,
            uploaded_by,
        )
        return entry


def rollback(file_type: str, *, user: str) -> int:
    """
    Restore the previous version (next-lower version number) as active.

    Raises ValueError if there is nothing to roll back to (no active
    version, or the active version is already the earliest).
    """
    with _lock:
        manifest = read_manifest(file_type)
        active = manifest.get("active_version")
        if active is None:
            raise ValueError("No active uploaded version to roll back from")
        earlier = [v["version"] for v in manifest["versions"] if v["version"] < active]
        if not earlier:
            raise ValueError("No earlier version to roll back to")
        target = max(earlier)
        manifest["active_version"] = target
        manifest["audit_log"].append(
            {
                "action": "rolled_back",
                "timestamp": _now(),
                "user": user,
                "version": target,
                "detail": f"rolled back from v{active} to v{target}",
            }
        )
        _write_manifest(file_type, manifest)
        logger.info("rollback[%s]: v%d -> v%d by %s", file_type, active, target, user)
        return target


def record_rejection(
    file_type: str,
    *,
    user: str,
    original_filename: str,
    error_count: int,
) -> None:
    """Record a rejected upload in the audit log (no file retained)."""
    with _lock:
        manifest = read_manifest(file_type)
        manifest["audit_log"].append(
            {
                "action": "rejected",
                "timestamp": _now(),
                "user": user,
                "version": None,
                "detail": (
                    f"rejected {original_filename!r} "
                    f"({error_count} validation error(s))"
                ),
            }
        )
        _write_manifest(file_type, manifest)
