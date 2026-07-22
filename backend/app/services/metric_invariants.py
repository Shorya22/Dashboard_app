"""
Metric invariants — relationships between measures that must ALWAYS hold.

This exists because of a real bug class: two different functions each
computed "Strategic Pool" (one from `Status`, one from a blank
`DOJ (DEPT)`), both rendered under the same label on different pages.
They agreed for months purely because the underlying rows coincided, then
a new roster arrived where they didn't and Home showed 1 while HR Home
showed 3. Nothing failed — the numbers just quietly disagreed.

The lesson: a metric definition living in one place is necessary but not
sufficient. Something has to *assert* that the relationships between
metrics still hold when the DATA changes, not just when the code changes.

These invariants run in two places:
  1. the test suite, against the real files (catches code drift), and
  2. the upload pipeline, against each newly-uploaded file (catches data
     drift, at the moment it enters the system rather than weeks later
     when someone squints at a dashboard).

An invariant here must be STRUCTURALLY true — something that follows from
the definitions themselves, not something that merely happens to be true
of today's data. If a check can legitimately fail on valid data, it is a
business rule for the dataset contract, not an invariant.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

import pandas as pd

from app.services import roster_metrics

logger = logging.getLogger(__name__)


@dataclass
class InvariantResult:
    name: str
    ok: bool
    detail: str


# Each check takes the roster DataFrame and returns (ok, detail).
InvariantCheck = Callable[[pd.DataFrame], tuple[bool, str]]


def _same_label_same_number(df: pd.DataFrame) -> tuple[bool, str]:
    """
    "Strategic Pool" is shown on Home (Workforce Category) and HR Home
    (Status Split). Both must resolve to the identical number — this is
    the exact invariant whose absence caused the 1-vs-3 discrepancy.
    """
    canonical = roster_metrics.get_strategic_pool(df)
    in_status_split = roster_metrics.get_status_split(df)["Strategic Pool"]
    in_category_split = roster_metrics.get_workforce_category_split(df)[
        "Strategic Pool"
    ]
    ok = canonical == in_status_split == in_category_split
    return ok, (
        f"Strategic Pool: canonical={canonical}, "
        f"status_split={in_status_split}, category_split={in_category_split}"
    )


def _status_split_sums_to_total(df: pd.DataFrame) -> tuple[bool, str]:
    """
    `Status` holds exactly one value per employee, so its breakdown must
    account for every employee. A shortfall means a Status value exists
    that no bucket counts (e.g. a new status nobody added a getter for),
    which would silently vanish from the donut.
    """
    split = roster_metrics.get_status_split(df)
    total = roster_metrics.get_total_employees(df)
    summed = sum(split.values())
    ok = summed == total
    missing = ""
    if not ok:
        known = {"Active", "Inactive", "Strategic Pool"}
        unknown = sorted(set(df["Status"].dropna().unique()) - known)
        if unknown:
            missing = f"; unaccounted Status values: {unknown}"
    return ok, f"status_split sums to {summed}, total employees {total}{missing}"


def _category_split_matches_status(df: pd.DataFrame) -> tuple[bool, str]:
    """
    Home's Workforce Category donut is a subset view of the same Status
    facts, so each of its buckets must equal the Status-based number for
    that label. If they diverge, the two pages are telling different
    stories about the same people.
    """
    category = roster_metrics.get_workforce_category_split(df)
    status = roster_metrics.get_status_split(df)
    mismatched = {
        k: (v, status.get(k))
        for k, v in category.items()
        if k in status and v != status[k]
    }
    ok = not mismatched
    return ok, (
        "workforce_category_split agrees with status_split"
        if ok
        else f"mismatched buckets (category vs status): {mismatched}"
    )


def _active_plus_inactive_plus_pool_is_total(df: pd.DataFrame) -> tuple[bool, str]:
    """The three status measures must partition the roster exactly once."""
    active = roster_metrics.get_active_employees(df)
    inactive = roster_metrics.get_inactive_employees(df)
    pool = roster_metrics.get_strategic_pool(df)
    total = roster_metrics.get_total_employees(df)
    ok = active + inactive + pool == total
    return ok, (
        f"active={active} + inactive={inactive} + strategic_pool={pool} "
        f"= {active + inactive + pool}, total={total}"
    )


def _closing_headcount_is_present_workforce(df: pd.DataFrame) -> tuple[bool, str]:
    """
    Closing Headcount must equal Active + Strategic Pool.

    Both answer "how many people are here now", and they sit on the same
    Home page — the KPI and the Workforce Category donut. They disagreed
    (47 vs 38) while Closing Headcount was LWD-based and 9 Inactive
    employees had no LWD. Now that it is Status-scoped this holds by
    construction, and this check keeps it that way.
    """
    closing = roster_metrics.get_closing_headcount(df)
    present = roster_metrics.get_active_employees(
        df
    ) + roster_metrics.get_strategic_pool(df)
    ok = closing == present
    return ok, (
        f"closing_headcount={closing}, active+strategic_pool={present}"
    )


def _seniority_split_covers_present_workforce(df: pd.DataFrame) -> tuple[bool, str]:
    """
    The Workforce-by-Seniority donut must account for exactly the current
    workforce — same people as the other workforce cards on the page.
    """
    split = roster_metrics.get_workforce_by_seniority_category(df)
    summed = sum(split.values())
    present = roster_metrics.get_closing_headcount(df)
    ok = summed == present
    return ok, f"seniority split sums to {summed}, present workforce {present}"


ROSTER_INVARIANTS: dict[str, InvariantCheck] = {
    "closing_headcount_is_present_workforce": _closing_headcount_is_present_workforce,
    "seniority_split_covers_present_workforce": _seniority_split_covers_present_workforce,
    "strategic_pool_same_everywhere": _same_label_same_number,
    "status_split_sums_to_total": _status_split_sums_to_total,
    "category_split_matches_status": _category_split_matches_status,
    "status_measures_partition_roster": _active_plus_inactive_plus_pool_is_total,
}

INVARIANTS_BY_FILE_TYPE: dict[str, dict[str, InvariantCheck]] = {
    "roster": ROSTER_INVARIANTS,
}


def run_invariants(df: pd.DataFrame, file_type: str) -> list[InvariantResult]:
    """Run every invariant registered for a dataset; never raises."""
    results: list[InvariantResult] = []
    for name, check in INVARIANTS_BY_FILE_TYPE.get(file_type, {}).items():
        try:
            ok, detail = check(df)
        except Exception as exc:  # noqa: BLE001 - a broken check must not block
            logger.warning("invariant %s errored: %s", name, exc)
            results.append(
                InvariantResult(name=name, ok=True, detail=f"skipped ({exc})")
            )
            continue
        results.append(InvariantResult(name=name, ok=ok, detail=detail))
    return results


def violations(df: pd.DataFrame, file_type: str) -> list[InvariantResult]:
    return [r for r in run_invariants(df, file_type) if not r.ok]
