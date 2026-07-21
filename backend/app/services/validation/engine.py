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
# dtype token -> (pandera/pandas dtype or None, coerce?). "any" means no
# type check at all — for columns whose representation legitimately varies
# across exports (e.g. a display "Month" that's a real date in one export
# and the label "Jun 26" in another) AND that no code reads, so enforcing a
# type buys nothing and only risks rejecting valid files.
_DTYPE_MAP: dict[str, tuple[str | None, bool]] = {
    "string": ("object", False),
    "categorical": ("object", False),
    "int": ("int64", True),
    "float": ("float64", True),
    "date": ("datetime64[ns]", True),
    "bool": ("bool", True),
    "any": (None, False),
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
        # NB: `allowed_values` is intentionally NOT enforced here via
        # pandera's isin — a pandera check can only ever be a hard error,
        # but we want per-column severity (a new region/grade should warn,
        # not block). It's handled in `run_allowed_values_stage` instead.
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


def run_allowed_values_stage(df: pd.DataFrame, config: dict) -> list[ValidationIssue]:
    """
    Check closed-set columns against their `allowed_values`, at each
    column's configured severity.

    `allowed_values_severity` (per column) defaults to "error". Set it to
    "warning" for org-structure enums that legitimately grow over time
    (grade bands, regions, entities, markets) — an unrecognized value is
    then surfaced for review instead of blocking the whole upload and
    freezing the dashboard. System-fixed sets (Status, Type, ...) keep
    the default error severity. Null values are skipped here — nullability
    is the schema stage's job.
    """
    issues: list[ValidationIssue] = []
    for col in config["columns"]:
        allowed = col.get("allowed_values")
        if not allowed or col["name"] not in df.columns:
            continue
        severity = Severity(col.get("allowed_values_severity", "error"))
        allowed_set = set(allowed)
        series = df[col["name"]]
        bad = series.notna() & ~series.isin(allowed_set)
        for idx in df.index[bad]:
            issues.append(
                ValidationIssue(
                    stage=Stage.SCHEMA,
                    severity=severity,
                    reason=(
                        f"{series.at[idx]!r} is not one of the recognized "
                        f"{col['name']} values ({', '.join(map(str, allowed))})"
                    ),
                    column=col["name"],
                    row=int(idx),
                    rule="allowed_values",
                    value=series.at[idx],
                )
            )
    return issues


def default_fill_warnings(df: pd.DataFrame, config: dict) -> list[ValidationIssue]:
    """
    Warn for each blank cell that `apply_defaults` is about to fill.

    Filling a blank asserts a fact that wasn't in the file (e.g. "no
    recorded experience" -> 0), so it is never done silently — every
    substituted cell is reported so an admin can spot an omission that
    should have been real data.
    """
    issues: list[ValidationIssue] = []
    for col in config["columns"]:
        if "default" not in col or col["name"] not in df.columns:
            continue
        for idx in df.index[df[col["name"]].isna()]:
            issues.append(
                ValidationIssue(
                    stage=Stage.SCHEMA,
                    severity=Severity.WARNING,
                    reason=(
                        f"{col['name']} was empty — defaulted to "
                        f"{col['default']!r}"
                    ),
                    column=col["name"],
                    row=int(idx),
                    rule="defaulted_value",
                    value=col["default"],
                )
            )
    return issues


def apply_defaults(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """
    Fill blanks in columns that declare a `default:` in the config.

    Applied both during validation (so downstream checks see the same
    values the dashboard will) and at load time in `data_loader`, so the
    contract's defaults are the single definition of "what an empty cell
    means" rather than being reimplemented per metric.
    """
    filled = df
    for col in config["columns"]:
        name = col["name"]
        if "default" not in col or name not in filled.columns:
            continue
        if filled[name].isna().any():
            if filled is df:
                filled = df.copy()
            filled[name] = filled[name].fillna(col["default"])
    return filled


def apply_dataset_defaults(df: pd.DataFrame, file_type: str) -> pd.DataFrame:
    """`apply_defaults` keyed by file type — the entry point data_loader uses."""
    return apply_defaults(df, load_config(file_type))


def run_null_warnings_stage(df: pd.DataFrame, config: dict) -> list[ValidationIssue]:
    """
    Report blanks in columns marked `warn_if_null: true`.

    For columns the dashboard tolerates being empty (the metric code
    already skips or buckets blanks) we allow the upload through, but
    still surface each blank as a warning so an admin knows the record is
    incomplete rather than it passing silently. Columns whose blankness
    would silently corrupt a metric (e.g. NEW_EMP_ID, which is dropped by
    `nunique(dropna=True)` and would under-count headcount) stay
    `nullable: false` and remain hard errors.
    """
    issues: list[ValidationIssue] = []
    for col in config["columns"]:
        if not col.get("warn_if_null") or col["name"] not in df.columns:
            continue
        series = df[col["name"]]
        for idx in df.index[series.isna()]:
            issues.append(
                ValidationIssue(
                    stage=Stage.SCHEMA,
                    severity=Severity.WARNING,
                    reason=(
                        f"{col['name']} is empty — this employee will be "
                        f"left out of any metric based on it"
                    ),
                    column=col["name"],
                    row=int(idx),
                    rule="empty_optional_value",
                )
            )
    return issues


def run_schema_stage(df: pd.DataFrame, config: dict) -> list[ValidationIssue]:
    """
    Structural + type + uniqueness validation via pandera, plus
    unknown-column detection, closed-set (allowed_values) checks, and
    blank-value warnings. Returns all violations (lazy mode).
    """
    issues: list[ValidationIssue] = _unknown_columns_stage(df, config)
    issues.extend(run_allowed_values_stage(df, config))
    issues.extend(run_null_warnings_stage(df, config))
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
