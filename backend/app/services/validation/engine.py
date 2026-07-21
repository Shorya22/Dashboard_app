"""
The generic, dataset-agnostic validation engine.

This module knows *how* to turn a YAML dataset config into a
`pandera.DataFrameSchema` and run it — it contains no knowledge of any
specific column, allowed value, or rule. All of that lives in the
per-dataset YAML files under `configs/`. Adding a new allowed GRADE
value, a new required column, or a whole new dataset never touches this
file.

Pipeline responsibilities that live here: config loading/caching, schema
construction, and the schema + business-rule validation stages
(structural, type, allowed-values, uniqueness, then the config's
cross-field rules). File-level security and cross-dataset checks live in
their own modules and are orchestrated by `pipeline.py`.
"""

from __future__ import annotations

import functools
from pathlib import Path

import pandas as pd
import pandera as pa
import yaml

from app.services.validation.report import Severity, Stage, ValidationIssue
from app.services.validation.rules import run_business_rules

CONFIG_DIR = Path(__file__).resolve().parent / "configs"

# Config dtype token -> (pandas/pandera dtype, coerce?). "string"/"categorical"
# map to numpy object so a nullable text column with blank (NaN) cells is
# handled safely — coercing to a strict str dtype would turn NaN into the
# literal "nan" and break nullable columns. Value-level correctness for
# text columns is enforced by `allowed_values` and business rules, not by
# a strict element-type check.
_DTYPE_MAP: dict[str, tuple[str, bool]] = {
    "string": ("object", False),
    "categorical": ("object", False),
    "int": ("int64", True),
    "float": ("float64", True),
    "date": ("datetime64[ns]", True),
    "bool": ("bool", True),
}


@functools.lru_cache(maxsize=None)
def load_config(file_type: str) -> dict:
    """
    Load and cache a dataset's YAML config by file type (e.g. "roster").

    Cached because configs are static per process and read on every
    validation. Raises FileNotFoundError for an unknown file type — the
    set of valid file types is exactly the set of YAML files present.
    """
    path = CONFIG_DIR / f"{file_type}.yaml"
    if not path.exists():
        raise FileNotFoundError(
            f"No validation config for file_type {file_type!r} (expected {path})"
        )
    with path.open("r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)
    _validate_config_shape(config, file_type)
    return config


def available_file_types() -> list[str]:
    """Every file type that has a config — the set of uploadable datasets."""
    return sorted(p.stem for p in CONFIG_DIR.glob("*.yaml"))


def _validate_config_shape(config: dict, file_type: str) -> None:
    """Fail loudly at load time if a config is malformed (developer error)."""
    for key in ("file_type", "schema_version", "columns"):
        if key not in config:
            raise ValueError(f"Config {file_type!r} missing required key {key!r}")
    if config["file_type"] != file_type:
        raise ValueError(
            f"Config file_type {config['file_type']!r} does not match "
            f"filename {file_type!r}"
        )
    for col in config["columns"]:
        if "name" not in col or "dtype" not in col:
            raise ValueError(f"Config {file_type!r} has a column missing name/dtype")
        if col["dtype"] not in _DTYPE_MAP:
            raise ValueError(
                f"Config {file_type!r} column {col.get('name')!r} has unknown "
                f"dtype {col['dtype']!r}; known: {sorted(_DTYPE_MAP)}"
            )


def build_schema(config: dict) -> pa.DataFrameSchema:
    """Build a pandera schema from a dataset config's `columns:` block."""
    columns: dict[str, pa.Column] = {}
    for col in config["columns"]:
        dtype, coerce = _DTYPE_MAP[col["dtype"]]
        checks: list[pa.Check] = []
        if "allowed_values" in col:
            checks.append(pa.Check.isin(col["allowed_values"]))
        if "min" in col:
            checks.append(pa.Check.ge(col["min"]))
        if "max" in col:
            checks.append(pa.Check.le(col["max"]))
        columns[col["name"]] = pa.Column(
            dtype,
            checks=checks or None,
            nullable=col.get("nullable", True),
            unique=col.get("unique", False),
            required=col.get("required", True),
            coerce=coerce,
        )
    # strict=False: we detect and report unknown columns ourselves (below)
    # so we can classify them per-config rather than raise pandera's blunt
    # "column not in schema" for every extra column.
    return pa.DataFrameSchema(columns, strict=False, coerce=False)


# Human-readable reasons for pandera's built-in check names, so a
# non-technical admin sees "value not in the allowed list" rather than
# "isin(...)". Falls back to the raw check string for anything unmapped.
_CHECK_REASONS = {
    "coerce_dtype": "value is not the expected type",
    "dtype": "column is not the expected type",
    "not_nullable": "value is missing (blank) but this column is required",
    "field_uniqueness": "duplicate value in a column that must be unique",
    "isin": "value is not one of the allowed values",
    "greater_than_or_equal_to": "value is below the allowed minimum",
    "less_than_or_equal_to": "value is above the allowed maximum",
}


def _reason_for_check(check: str) -> str:
    for key, reason in _CHECK_REASONS.items():
        if check.startswith(key):
            return f"{reason} ({check})"
    return check


def _unknown_columns_stage(
    df: pd.DataFrame, config: dict
) -> list[ValidationIssue]:
    """
    Report columns present in the file but not defined in the config.

    Default severity is ERROR (an unknown column signals a wrong file or
    an undocumented schema change); a config may set
    `allow_unknown_columns: true` to downgrade this to a warning.
    """
    known = {c["name"] for c in config["columns"]}
    extras = [c for c in df.columns if c not in known]
    if not extras:
        return []
    severity = (
        Severity.WARNING if config.get("allow_unknown_columns") else Severity.ERROR
    )
    return [
        ValidationIssue(
            stage=Stage.SCHEMA,
            severity=severity,
            reason=(
                f"Unexpected column {name!r} is not part of the "
                f"{config['file_type']} contract"
            ),
            column=name,
            rule="unknown_column",
        )
        for name in extras
    ]


def run_schema_stage(df: pd.DataFrame, config: dict) -> list[ValidationIssue]:
    """
    Structural + type + allowed-value + uniqueness validation via pandera,
    plus unknown-column detection. Returns all violations (lazy mode).
    """
    issues: list[ValidationIssue] = _unknown_columns_stage(df, config)
    schema = build_schema(config)
    try:
        schema.validate(df, lazy=True)
    except pa.errors.SchemaErrors as exc:
        for _, case in exc.failure_cases.iterrows():
            check = str(case.get("check"))
            raw_idx = case.get("index")
            row = int(raw_idx) if isinstance(raw_idx, (int, float)) and pd.notna(raw_idx) else None
            column = None if pd.isna(case.get("column")) else str(case.get("column"))
            failure_case = case.get("failure_case")
            # For a missing required column, pandera reports the column
            # name in `failure_case` (not `column`) — surface it clearly.
            if check == "column_in_dataframe":
                issues.append(
                    ValidationIssue(
                        stage=Stage.SCHEMA,
                        severity=Severity.ERROR,
                        reason=f"Required column {failure_case!r} is missing",
                        column=str(failure_case),
                        rule="missing_required_column",
                        value=None,
                    )
                )
                continue
            issues.append(
                ValidationIssue(
                    stage=Stage.SCHEMA,
                    severity=Severity.ERROR,
                    reason=_reason_for_check(check),
                    column=column,
                    row=row,
                    rule=check,
                    value=failure_case,
                )
            )
    return issues


def run_business_stage(df: pd.DataFrame, config: dict) -> list[ValidationIssue]:
    """Run the config's cross-field business rules (all of them, collected)."""
    return run_business_rules(df, config.get("business_rules", []))
