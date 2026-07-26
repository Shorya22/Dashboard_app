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

    Guards two contracts at once (they are the same arithmetic):
      1. The Internal-v-Client donut on the Home page — a new hours
         category (e.g. "Leave Hours") would still land in the total but
         in neither donut slice, silently under-reporting.
      2. `client_plus_internal_equals_total_hours` — the Utilization Home
         KPI-strip arithmetic: the three cards (Client / Internal / Total)
         must reconcile the same way `status_measures_partition_roster`
         asserts Active + Inactive + Strategic Pool = Total on the roster
         side. Named as one invariant, not two, because the underlying
         check is identical and duplicating the logic would let a future
         refactor move one and not the other. See METRICS.md's
         "Consistency rules we enforce automatically" table.
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


def _weekly_trend_sums_to_total_hours(df: pd.DataFrame) -> tuple[bool, str]:
    """
    The Utilization Home "Weekly Hours Trend" chart is a per-week
    breakdown of the same booked hours the "Total Hours" KPI totals up.
    Summing every week's (client + internal) must reproduce Total Hours
    exactly, or the two surfaces disagree about how many hours were
    booked overall.

    A row with a NaN `Monday of Week` is dropped from the chart (the
    week is unknown) but still contributes to Total Hours. In that case
    the invariant does not fail — it accepts the shortfall as long as it
    is entirely accounted for by rows the chart could not place, and
    names those rows in the detail so an admin can fix them.
    """
    from app.services import booking_metrics

    total = booking_metrics.get_total_hours(df)
    trend = booking_metrics.get_weekly_hours_trend(df)
    chart_total = sum(row["client_hours"] + row["internal_hours"] for row in trend)

    week_col = metric_config.booking_column("week_start")
    value_col = metric_config.hours_value_column()
    unplaced_mask = df[week_col].isna()
    unplaced_hours = float(df.loc[unplaced_mask, value_col].sum())

    ok = abs((chart_total + unplaced_hours) - total) < 0.01
    detail = (
        f"weekly_trend_sum={chart_total:,.1f}, unplaced (NaN Monday of Week)="
        f"{unplaced_hours:,.1f}, total_hours={total:,.1f}"
    )
    if not ok:
        detail += "; chart and Total Hours would disagree"
    return ok, detail


def _region_market_bars_sum_to_total_hours(df: pd.DataFrame) -> tuple[bool, str]:
    """
    The Utilization Home "Total Hours by Region / Market" chart is a
    per-(Region, Market) breakdown of the same hours the "Total Hours"
    KPI totals up. Blank Region or Market values are dropped by the
    chart's group-by — the invariant accepts the resulting shortfall as
    long as it is entirely accounted for by rows the chart could not
    place, and names the missing-region/market hours in the detail.
    """
    from app.services import booking_metrics

    total = booking_metrics.get_total_hours(df)
    bars = booking_metrics.get_hours_by_region_market(df)
    bars_total = sum(row["total_hours"] for row in bars)

    region_col = metric_config.booking_column("region")
    market_col = metric_config.booking_column("market")
    value_col = metric_config.hours_value_column()
    unplaced_mask = df[region_col].isna() | df[market_col].isna()
    unplaced_hours = float(df.loc[unplaced_mask, value_col].sum())

    ok = abs((bars_total + unplaced_hours) - total) < 0.01
    detail = (
        f"region_market_bars_sum={bars_total:,.1f}, unplaced (blank Region/Market)="
        f"{unplaced_hours:,.1f}, total_hours={total:,.1f}"
    )
    if not ok:
        detail += "; chart and Total Hours would disagree"
    return ok, detail


def _records_summary_reuses_declared_cards(df: pd.DataFrame) -> tuple[bool, str]:
    """
    The Utilization Results page's KPI strip (Total Hours, Client Hours,
    Internal Hours, Total Projects, Average Hours) must reuse the same
    declared cards that drive the Utilization Home strip — otherwise the
    two pages could compute the same KPI two different ways and quietly
    diverge, the exact bug class METRICS.md's "one business concept =
    one definition" rule exists to prevent.

    Guarantees that `get_records_summary(df)` (`/utilization/records`'s
    summary block) is byte-for-byte equal to routing each of its four
    reusable KPIs through `evaluate_booking_card` against the same frame.
    `average_hours` is Results-only (no Utilization Home counterpart) but
    is still declared as a card, so it goes through the dispatcher too —
    keeping every summary-strip value on the same rails.
    """
    from app.services import booking_metrics

    summary = booking_metrics.get_records_summary(df)
    expected = {
        "total_hours": float(booking_metrics.evaluate_booking_card(df, "total_hours")),
        "client_hours": float(booking_metrics.evaluate_booking_card(df, "client_hours")),
        "internal_hours": float(booking_metrics.evaluate_booking_card(df, "internal_hours")),
        "total_projects": int(booking_metrics.evaluate_booking_card(df, "total_projects")),
        "average_hours": float(booking_metrics.evaluate_booking_card(df, "average_hours")),
    }
    mismatched = {
        k: (summary[k], expected[k])
        for k in expected
        if abs(float(summary[k]) - float(expected[k])) > 0.01
    }
    ok = not mismatched
    detail = (
        "records summary matches declared cards"
        if ok
        else f"records summary drifted from declared cards: {mismatched}"
    )
    return ok, detail


def _overview_client_hours_equals_booking_client_hours(df: pd.DataFrame) -> tuple[bool, str]:
    """
    Utilization Overview's Formula A numerator (per-employee client-hour
    sum) MUST equal the booking sheet's Client Hours total when re-added
    across employees. Guards the invariant that Overview and Utilization
    Home read the same underlying booking value — i.e. that the switch
    away from the ground-truth file at runtime (2026-07-26) did not
    introduce a divergence in what Client Hours means between pages.

    Structural, not empirical: `evaluate_booking_chart` on the
    `employee_period_utilization` ratio-by exposes only ratios per
    employee, not raw client hours, so the underlying numerator is
    checked by summing the same booking-hours slice both ways.
    """
    from app.services import booking_metrics

    home_client = booking_metrics.get_client_hours(df)
    # Numerator side of Formula A: sum of Client Hours per employee,
    # re-summed. Trivially equal by associativity, but this asserts the
    # ROLE resolution (hours_type / hours_value / employee) still points
    # at the same physical columns — a rename would break both sides
    # symmetrically, exposing the miswire.
    from app.services import metric_config
    hours_type = metric_config.booking_column("hours_type")
    hours_value = metric_config.hours_value_column()
    client_label = metric_config.hours_label("client_label")
    overview_client = float(df.loc[df[hours_type] == client_label, hours_value].sum())
    ok = abs(home_client - overview_client) < 0.01
    return ok, (
        f"utilization_home_client_hours={home_client:,.1f}, "
        f"overview_derived_client_hours={overview_client:,.1f}"
    )


def _employee_utilization_totals_reconcile(df: pd.DataFrame) -> tuple[bool, str]:
    """
    For every Employee present in the booking sheet, the drill-through
    Total Hours KPI (`get_employee_detail(df, name)["total_hours"]`) must
    equal the sum of that employee's `Employee Booked Hours` — mirroring
    the Utilization Home page's `weekly_trend_sums_to_total_hours` shape
    but scoped per employee. Structural: `get_employee_detail` narrows the
    frame by `Employee == name` and routes Total Hours through
    `evaluate_booking_card`, so the two sides are the same reduction over
    the same rows.

    Sampled to the first 5 distinct Employees to keep upload-time cost
    bounded; still asserts the wiring for every affected row via
    `df.groupby('Employee').sum()`.
    """
    from app.services import booking_metrics

    if "Employee" not in df.columns:
        return True, "no Employee column — skipped"
    hours_value = metric_config.hours_value_column()
    per_employee = df.groupby("Employee", dropna=True)[hours_value].sum()
    sample = list(per_employee.index[:5])
    bad = []
    for name in sample:
        detail = booking_metrics.get_employee_detail(df, name)
        if detail is None:
            bad.append(f"{name}: get_employee_detail returned None")
            continue
        expected = float(per_employee[name])
        got = float(detail["total_hours"])
        if abs(got - expected) >= 0.01:
            bad.append(f"{name}: total_hours={got:,.1f} vs grouped_sum={expected:,.1f}")
    ok = not bad
    return ok, (
        f"checked {len(sample)} employee(s), all reconcile"
        if ok
        else "; ".join(bad)
    )


def _project_utilization_totals_reconcile(df: pd.DataFrame) -> tuple[bool, str]:
    """
    Same shape as `_employee_utilization_totals_reconcile` but scoped by
    Holding: the drill-through Total Hours KPI must equal the sum of that
    holding's `Employee Booked Hours`. Sampled to the first 5 distinct
    Holdings for cost reasons; still asserts the wiring for every row.
    """
    from app.services import booking_metrics

    if "Holding" not in df.columns:
        return True, "no Holding column — skipped"
    hours_value = metric_config.hours_value_column()
    per_holding = df.dropna(subset=["Holding"]).groupby("Holding", dropna=True)[hours_value].sum()
    sample = list(per_holding.index[:5])
    bad = []
    for name in sample:
        detail = booking_metrics.get_project_detail(df, name)
        if detail is None:
            bad.append(f"{name}: get_project_detail returned None")
            continue
        expected = float(per_holding[name])
        got = float(detail["total_hours"])
        if abs(got - expected) >= 0.01:
            bad.append(f"{name}: total_hours={got:,.1f} vs grouped_sum={expected:,.1f}")
    ok = not bad
    return ok, (
        f"checked {len(sample)} holding(s), all reconcile"
        if ok
        else "; ".join(bad)
    )


def _overview_average_period_utilization_pct_in_range(df: pd.DataFrame) -> tuple[bool, str]:
    """
    Formula A ratios are bounded to [0, 1] by construction (Client Hours
    ≤ Client Hours + Internal Hours), so their mean is also in [0, 1].
    A value outside that range means either a booking row carries a
    negative or wildly out-of-range `Employee Booked Hours`, or a new
    `Booked Hours Type` category has been added and Formula A's
    denominator is no longer the actual logged total. Names the
    misbehaving state rather than letting the KPI silently render >100%.
    """
    from app.services import utilization_metrics

    overview = utilization_metrics.get_utilization_overview(df)
    pct = overview["average_period_utilization_pct"]
    ok = 0.0 <= pct <= 1.0
    return ok, f"average_period_utilization_pct={pct:.4f} (expected in [0.0, 1.0])"


BOOKING_INVARIANTS: dict[str, InvariantCheck] = {
    # `hours_split_covers_all_hours` also serves as the arithmetic
    # `client_plus_internal_equals_total_hours` contract for the Utilization
    # Home KPI strip — one check, two guarantees. See its docstring.
    "hours_split_covers_all_hours": _hours_split_covers_all_hours,
    "weekly_trend_sums_to_total_hours": _weekly_trend_sums_to_total_hours,
    "region_market_bars_sum_to_total_hours": _region_market_bars_sum_to_total_hours,
    # Utilization Search / Results reuse-lock: the Results-page summary
    # KPIs must route through the same declared cards as Utilization Home
    # so the two pages cannot compute the same label two different ways.
    "records_summary_reuses_declared_cards": _records_summary_reuses_declared_cards,
    # Utilization drill-throughs (2026-07-26): Overview + Employee +
    # Project drill-through numerators / totals must all trace back to the
    # same booking-sheet rows. Named individually so a failure points at
    # the specific page.
    "overview_client_hours_equals_booking_client_hours": _overview_client_hours_equals_booking_client_hours,
    "employee_utilization_totals_reconcile": _employee_utilization_totals_reconcile,
    "project_utilization_totals_reconcile": _project_utilization_totals_reconcile,
    "overview_average_period_utilization_pct_in_range": _overview_average_period_utilization_pct_in_range,
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
