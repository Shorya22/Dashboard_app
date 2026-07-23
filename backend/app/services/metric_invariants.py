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

from app.services import metric_config, roster_metrics

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
    in_status_split = roster_metrics.get_status_split(df).get("Strategic Pool", 0)
    in_category_split = roster_metrics.get_workforce_category_split(df).get(
        "Strategic Pool", 0
    )
    ok = canonical == in_status_split == in_category_split
    return ok, (
        f"Strategic Pool: canonical={canonical}, "
        f"status_split={in_status_split}, category_split={in_category_split}"
    )


def _every_status_has_a_workforce_meaning(df: pd.DataFrame) -> tuple[bool, str]:
    """
    Every `Status` in the data must be known to mean either "still here"
    or "gone".

    The donut itself needs no configuration — it simply reflects whatever
    statuses the column contains, so a new one appears on its own. But
    one question can't be read off the data: does a person with that
    status still count as part of the workforce? Until that's answered
    they sit in Total Employees yet outside Closing Headcount, which is
    a real (if conservative) inconsistency worth naming.
    """
    from app.services import metric_config

    split = roster_metrics.get_status_split(df)
    total = roster_metrics.get_total_employees(df)
    summed = sum(split.values())

    accounted = set(metric_config.present_statuses()) | {
        metric_config.status_value("inactive")
    }
    unknown = sorted(set(split) - accounted)
    ok = summed == total and not unknown
    detail = f"status_split sums to {summed}, total employees {total}"
    if unknown:
        detail += (
            f"; new Status value(s) {unknown} — not currently counted as part "
            "of the workforce. If they should be, add them to "
            "status.counts_as_present"
        )
    return ok, detail


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


def _charts_account_for_everyone(df: pd.DataFrame) -> tuple[bool, str]:
    """
    Every breakdown chart must add up to the population it describes.

    A group-by silently drops blanks, so a roster with an empty Region
    cell used to produce bars totalling less than the headline card above
    them — with nothing on screen to explain the gap. Charts now count
    blanks under a "TBD" label; this asserts the totals really do
    reconcile, for each chart's declared scope.
    """
    from app.services import metric_config

    bad: list[str] = []
    for name in metric_config.chart_names():
        spec = metric_config.chart(name)
        # Only the group-by charts partition the population and so must
        # reconcile to a total. A `monthly_series` is a time series (one
        # row per month, returned as a list), not a partition — summing it
        # is meaningless, so it is skipped here.
        if spec["type"] == "monthly_series":
            continue
        # Target = the distinct employees in the chart's OWN scope, derived
        # the same way the chart derives it, so every scope (all / present /
        # exited) is handled uniformly with no hardcoded lookup.
        scope_df = roster_metrics._chart_scope(df, spec)
        target = roster_metrics.get_total_employees(scope_df)
        counted = sum(roster_metrics.evaluate_chart(df, name).values())
        if counted != target:
            bad.append(
                f"{name}={counted} vs {spec.get('scope', 'all')} total {target}"
            )
    return not bad, ("all charts reconcile" if not bad else "; ".join(bad))


def _exits_equals_inactive(df: pd.DataFrame) -> tuple[bool, str]:
    """
    Exits and Inactive are the same people, so they must be the same
    number (confirmed 2026-07-22).

    They used to disagree — 5 vs 14 — because Exits was counted from LWD
    dates while Inactive came from Status, and 9 employees are marked
    Inactive with no last working day recorded. One definition now; this
    keeps it that way.
    """
    exits = roster_metrics.get_exits(df)
    inactive = roster_metrics.get_inactive_employees(df)
    ok = exits == inactive
    return ok, f"exits={exits}, inactive={inactive}"


def _every_exit_has_a_leaving_date(df: pd.DataFrame) -> tuple[bool, str]:
    """
    Every exit should have an `LWD`, so the monthly leavers trend can
    account for all of them.

    Exits is a Status count (14 today) but the month-by-month trend is
    built from leaving dates, so an Inactive employee with no `LWD` can
    never appear in it — the card and the chart then describe different
    totals. This is a data gap, not a code one: filling in the dates
    closes it, and the row-level warnings on the upload name exactly who
    is missing.
    """
    exits = roster_metrics.get_exits(df)
    dated = roster_metrics.get_dated_exits(df)
    ok = exits == dated
    detail = f"exits={exits}, of which {dated} have a leaving date"
    if not ok:
        detail += (
            f"; {exits - dated} exit(s) have no LWD, so the monthly leavers "
            "trend and the Voluntary/Involuntary split cannot include them"
        )
    return ok, detail


ROSTER_INVARIANTS: dict[str, InvariantCheck] = {
    "charts_account_for_everyone": _charts_account_for_everyone,
    "exits_equals_inactive": _exits_equals_inactive,
    "every_exit_has_a_leaving_date": _every_exit_has_a_leaving_date,
    "closing_headcount_is_present_workforce": _closing_headcount_is_present_workforce,
    "seniority_split_covers_present_workforce": _seniority_split_covers_present_workforce,
    "strategic_pool_same_everywhere": _same_label_same_number,
    "every_status_has_a_workforce_meaning": _every_status_has_a_workforce_meaning,
    "category_split_matches_status": _category_split_matches_status,
    "status_measures_partition_roster": _active_plus_inactive_plus_pool_is_total,
}

def _hours_split_covers_all_hours(df: pd.DataFrame) -> tuple[bool, str]:
    """
    Client Hours + Internal Hours must equal total booked hours.

    The Internal-v-Client donut splits on two configured labels. If the
    source ever adds or renames a category (e.g. "Leave Hours"), those
    hours would still land in the total but in neither slice — the donut
    would quietly under-report with nothing on screen to indicate it.
    This turns that into a visible warning at upload time.
    """
    from app.services import booking_metrics

    total = booking_metrics.get_total_hours(df)
    client = booking_metrics.get_client_hours(df)
    internal = booking_metrics.get_internal_hours(df)
    ok = abs((client + internal) - total) < 0.01
    detail = f"client={client:,.1f} + internal={internal:,.1f} vs total={total:,.1f}"
    if not ok:
        known = {
            booking_metrics.CLIENT_HOURS_LABEL,
            booking_metrics.INTERNAL_HOURS_LABEL,
        }
        extra = sorted(set(df[metric_config.hours_type_column()].dropna()) - known)
        detail += f"; unaccounted Booked Hours Type values: {extra}"
    return ok, detail


BOOKING_INVARIANTS: dict[str, InvariantCheck] = {
    "hours_split_covers_all_hours": _hours_split_covers_all_hours,
}

INVARIANTS_BY_FILE_TYPE: dict[str, dict[str, InvariantCheck]] = {
    "roster": ROSTER_INVARIANTS,
    "booking": BOOKING_INVARIANTS,
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
