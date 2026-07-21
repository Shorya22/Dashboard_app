"""
Phase 8 data-ingestion validation package.

Config-driven: the engine (`engine.py`, `rules.py`) is generic and holds
no dataset-specific knowledge — every column, allowed value, and rule
lives in a per-dataset YAML file under `configs/`. See PLAN.md Phase 8.

Public entry points:
- `validate_file(...)` — run the full pipeline on an uploaded file.
- `load_config(file_type)` / `available_file_types()` — read the contract.
- `sha256_file(...)` — fingerprint for idempotency.
"""

from app.services.validation.engine import available_file_types, load_config
from app.services.validation.fingerprint import sha256_bytes, sha256_file
from app.services.validation.pipeline import validate_file
from app.services.validation.report import (
    Severity,
    Stage,
    ValidationIssue,
    ValidationReport,
)

__all__ = [
    "validate_file",
    "load_config",
    "available_file_types",
    "sha256_file",
    "sha256_bytes",
    "ValidationReport",
    "ValidationIssue",
    "Severity",
    "Stage",
]
