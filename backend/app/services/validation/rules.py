"""
Generic, dataset-agnostic business-rule evaluators.

Each evaluator implements one *kind* of cross-field rule (sum-of-columns,
conditional-presence, constant-per-group, ...). None of them contain any
dataset-specific knowledge — the column names, tolerances, allowed tokens
and severities all arrive as parameters from a YAML config's
`business_rules:` list. Adding a new GRADE value or a new roster rule of
an existing kind is a config edit; only a genuinely new *kind* of rule
needs a new evaluator here.

Every evaluator has the same signature::

    def evaluator(df: pd.DataFrame, rule: dict) -> list[ValidationIssue]

and reports problems as `ValidationIssue`s rather than raising, so one
bad file yields one issue per offending row instead of stopping at the
first. Register a new kind by adding it to `RULE_EVALUATORS`.
"""

from __future__ import annotations

import warnings
from typing import Callable

import pandas as pd

from app.services.validation.report import Severity, Stage, ValidationIssue


def _to_datetime_quiet(series: pd.Series) -> pd.Series:
    """
    Parse mixed date strings without pandas' noisy "could not infer
    format" UserWarning — expected here since source date columns hold
    mixed formats and sentinel tokens like "TBD".
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return pd.to_datetime(series, errors="coerce")


def _severity(rule: dict) -> Severity:
    return Severity(rule.get("severity", "error"))


def _missing_columns(df: pd.DataFrame, cols: list[str]) -> list[str]:
    return [c for c in cols if c not in df.columns]


def _skip_if_columns_missing(
    df: pd.DataFrame, rule: dict, cols: list[str]
) -> list[ValidationIssue] | None:
    """
    A business rule can only run if the columns it references exist. If
    any are missing that's already been reported as a schema-stage error
    (missing required column), so here we simply skip the rule rather
    than double-reporting or crashing on a KeyError.
    """
    missing = _missing_columns(df, cols)
    if missing:
        return []  # schema stage owns the "missing column" report
    return None


def sum_equals(df: pd.DataFrame, rule: dict) -> list[ValidationIssue]:
    """
    `target` must equal the sum of `addends` within `tolerance`.

    e.g. Total Experience == Hexaware Experience + Before Hexaware
    Experience (tolerance 0.01). Rows where any operand is non-numeric
    are reported as errors rather than silently coerced.
    """
    target = rule["target"]
    addends = rule["addends"]
    tol = float(rule.get("tolerance", 0.0))
    sev = _severity(rule)

    skip = _skip_if_columns_missing(df, rule, [target, *addends])
    if skip is not None:
        return skip

    numeric = {c: pd.to_numeric(df[c], errors="coerce") for c in [target, *addends]}
    computed = sum(numeric[a] for a in addends)
    diff = (computed - numeric[target]).abs()
    # A NaN diff means some operand didn't parse as a number -> also a violation.
    bad = diff.isna() | (diff > tol)

    issues: list[ValidationIssue] = []
    for idx in df.index[bad]:
        issues.append(
            ValidationIssue(
                stage=Stage.BUSINESS,
                severity=sev,
                reason=rule["reason"],
                column=target,
                row=int(idx),
                rule=rule["name"],
                value=df.at[idx, target],
            )
        )
    return issues


def conditional_presence(df: pd.DataFrame, rule: dict) -> list[ValidationIssue]:
    """
    When `when_column` equals `when_equals` (or is in `when_in`),
    `then_column` must be present (non-null) or absent (null),
    per `then` = "present" | "absent".

    e.g. LWD must be present when Status == "Inactive".
    """
    when_col = rule["when_column"]
    then_col = rule["then_column"]
    expect = rule["then"]  # "present" | "absent"
    sev = _severity(rule)

    skip = _skip_if_columns_missing(df, rule, [when_col, then_col])
    if skip is not None:
        return skip

    if "when_in" in rule:
        condition = df[when_col].isin(rule["when_in"])
    else:
        condition = df[when_col] == rule["when_equals"]

    is_present = df[then_col].notna() & (df[then_col].astype(str).str.strip() != "")
    if expect == "present":
        violating = condition & ~is_present
    elif expect == "absent":
        violating = condition & is_present
    else:  # pragma: no cover - guarded by config validation
        raise ValueError(f"conditional_presence: bad 'then' value {expect!r}")

    issues: list[ValidationIssue] = []
    for idx in df.index[violating]:
        issues.append(
            ValidationIssue(
                stage=Stage.BUSINESS,
                severity=sev,
                reason=rule["reason"],
                column=then_col,
                row=int(idx),
                rule=rule["name"],
                value=df.at[idx, then_col],
            )
        )
    return issues


def constant_per_group(df: pd.DataFrame, rule: dict) -> list[ValidationIssue]:
    """
    `value_column` must be constant across all rows sharing the same
    `group_by` key.

    e.g. Period Total Utilization % must be identical for every week-row
    of a given Employee.
    """
    group_by = rule["group_by"]
    value_col = rule["value_column"]
    sev = _severity(rule)
    tol = float(rule.get("tolerance", 0.0))

    skip = _skip_if_columns_missing(df, rule, [group_by, value_col])
    if skip is not None:
        return skip

    issues: list[ValidationIssue] = []
    for key, grp in df.groupby(group_by):
        vals = grp[value_col]
        if pd.api.types.is_numeric_dtype(vals):
            spread = vals.max() - vals.min()
            inconsistent = pd.notna(spread) and spread > tol
        else:
            inconsistent = vals.nunique(dropna=True) > 1
        if inconsistent:
            for idx in grp.index:
                issues.append(
                    ValidationIssue(
                        stage=Stage.BUSINESS,
                        severity=sev,
                        reason=rule["reason"],
                        column=value_col,
                        row=int(idx),
                        rule=rule["name"],
                        value=df.at[idx, value_col],
                    )
                )
    return issues


def date_or_token(df: pd.DataFrame, rule: dict) -> list[ValidationIssue]:
    """
    Every value in `column` must either parse as a date or be one of
    `allowed_tokens` (e.g. "TBD"). Nulls are allowed only if
    `allow_null` is true.

    e.g. DOJ (DEPT) must be a real date or the literal "TBD" — anything
    else would silently break date-based headcount math downstream.
    """
    col = rule["column"]
    tokens = set(rule.get("allowed_tokens", []))
    allow_null = bool(rule.get("allow_null", False))
    sev = _severity(rule)

    skip = _skip_if_columns_missing(df, rule, [col])
    if skip is not None:
        return skip

    series = df[col]
    parsed = _to_datetime_quiet(series)

    issues: list[ValidationIssue] = []
    for idx in df.index:
        raw = series.at[idx]
        if pd.isna(raw):
            if allow_null:
                continue
            ok = False
        elif str(raw).strip() in tokens:
            ok = True
        else:
            ok = pd.notna(parsed.at[idx])
        if not ok:
            issues.append(
                ValidationIssue(
                    stage=Stage.BUSINESS,
                    severity=sev,
                    reason=rule["reason"],
                    column=col,
                    row=int(idx),
                    rule=rule["name"],
                    value=raw,
                )
            )
    return issues


def date_within_offset(df: pd.DataFrame, rule: dict) -> list[ValidationIssue]:
    """
    `date_column` must fall within [base_column, base_column +
    max_offset_days], inclusive.

    e.g. Date must be within the same week as Monday of Week
    (0..6 days after it).
    """
    date_col = rule["date_column"]
    base_col = rule["base_column"]
    max_offset = int(rule["max_offset_days"])
    min_offset = int(rule.get("min_offset_days", 0))
    sev = _severity(rule)

    skip = _skip_if_columns_missing(df, rule, [date_col, base_col])
    if skip is not None:
        return skip

    date = _to_datetime_quiet(df[date_col])
    base = _to_datetime_quiet(df[base_col])
    delta_days = (date - base).dt.days
    # NaT-driven NaN delta = unparseable date on one side = violation.
    bad = delta_days.isna() | (delta_days < min_offset) | (delta_days > max_offset)

    issues: list[ValidationIssue] = []
    for idx in df.index[bad]:
        issues.append(
            ValidationIssue(
                stage=Stage.BUSINESS,
                severity=sev,
                reason=rule["reason"],
                column=date_col,
                row=int(idx),
                rule=rule["name"],
                value=df.at[idx, date_col],
            )
        )
    return issues


def unique_together(df: pd.DataFrame, rule: dict) -> list[ValidationIssue]:
    """
    The combination of `columns` must be unique across rows (a composite
    primary key). Flags every row that shares its key with another.

    e.g. (Employee, Week Start) must be unique in the ground-truth sheet
    — a duplicate would double-count that employee's week.
    """
    cols = rule["columns"]
    sev = _severity(rule)

    skip = _skip_if_columns_missing(df, rule, cols)
    if skip is not None:
        return skip

    dup_mask = df.duplicated(subset=cols, keep=False)
    issues: list[ValidationIssue] = []
    for idx in df.index[dup_mask]:
        key = ", ".join(f"{c}={df.at[idx, c]!r}" for c in cols)
        issues.append(
            ValidationIssue(
                stage=Stage.BUSINESS,
                severity=sev,
                reason=rule["reason"],
                column=cols[0],
                row=int(idx),
                rule=rule["name"],
                value=key,
            )
        )
    return issues


RULE_EVALUATORS: dict[str, Callable[[pd.DataFrame, dict], list[ValidationIssue]]] = {
    "sum_equals": sum_equals,
    "conditional_presence": conditional_presence,
    "constant_per_group": constant_per_group,
    "date_or_token": date_or_token,
    "date_within_offset": date_within_offset,
    "unique_together": unique_together,
}


def run_business_rules(df: pd.DataFrame, rules: list[dict]) -> list[ValidationIssue]:
    """Run every configured business rule, collecting all issues."""
    issues: list[ValidationIssue] = []
    for rule in rules:
        kind = rule["type"]
        evaluator = RULE_EVALUATORS.get(kind)
        if evaluator is None:
            raise ValueError(
                f"Unknown business-rule type {kind!r} in rule "
                f"{rule.get('name')!r}. Known types: {sorted(RULE_EVALUATORS)}"
            )
        issues.extend(evaluator(df, rule))
    return issues
