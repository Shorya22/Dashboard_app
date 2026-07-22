"""
Stand-in for the real Power BI model's `Calendar` / `Available Months`
tables, which don't exist as separate source files in this backend.

The real model uses a date-dimension table (`Calendar`, one row per day)
plus a derived `Available Months` table (one row per calendar month,
with a `Month Start` column) for period navigation. All the period-scoped
HR MASTER measures (`Closing Headcount`, `Opening Headcount`, `Joiners`,
`Exits`, and by extension `Attrition %`) filter against
`MIN`/`MAX('Available Months'[Month Start])` or `MIN('Calendar'[Date])`.

Since there is no separate calendar source file, this module derives an
equivalent date range directly from the roster data itself.

Boundary logic (documented here since there's no source file to point to):
  - Earliest date = MIN(`DOJ (DEPT)`) across all rows with a parseable
    date. This is the first date any employee is known to have joined
    their department, so it's the natural start of "all history we have
    data for."
  - Latest date = MAX of: the `Today` snapshot date, MAX(`DOJ (DEPT)`),
    and MAX(`LWD`). Using `Today` alone would truncate the range if any
    `LWD` or `DOJ (DEPT)` value happens to fall after the snapshot date
    (shouldn't happen in a clean export, but this is defensive); using
    the DOJ/LWD maxes alone would miss the current snapshot date if the
    most recent event is somewhat in the past.
  - `Available Months[Month Start]` = the set of first-of-month dates
    for every calendar month from `earliest_date` through `latest_date`,
    inclusive.
  - `Calendar[Date]` is only ever consumed by `Opening Headcount` via
    `MIN('Calendar'[Date])`, which this module exposes as
    `earliest_date` directly (the exact date, NOT rounded to a month
    start) — the real `Calendar` table is daily-grained, so its MIN is
    the earliest actual date in the range, not the 1st of that month.

Unparseable `DOJ (DEPT)`/`LWD` values (e.g. literal "TBD" strings,
confirmed present in the real file — see `roster_metrics.get_data_quality_warnings`)
are dropped (as NaT) before computing min/max here; they're already
surfaced separately as a data-quality warning and must not silently
distort the calendar boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass

import logging

import pandas as pd

logger = logging.getLogger(__name__)

DATE_FORMAT = "%d-%b-%y"  # source format, e.g. "24-Nov-25" — matches roster_metrics.DATE_FORMAT


@dataclass(frozen=True)
class AvailableMonths:
    """
    Equivalent of the real model's `Available Months` table plus the one
    `Calendar` field actually consumed (`MIN('Calendar'[Date])`).

    - `month_starts`: every `Month Start` value (first-of-month
      `pd.Timestamp`) from the earliest to latest relevant month,
      inclusive. Sorted ascending.
    - `earliest_date`: MIN('Calendar'[Date]) equivalent — the exact
      earliest date in the range (not rounded to a month start).
    - `latest_date`: the exact latest date in the range (used only to
      derive `month_starts`; the real model doesn't expose a MAX(Calendar[Date])
      consumer among the confirmed DAX formulas, but it's kept here for
      completeness/debugging).
    """

    month_starts: list[pd.Timestamp]
    earliest_date: pd.Timestamp | None
    latest_date: pd.Timestamp | None

    @property
    def min_month_start(self) -> pd.Timestamp:
        """MIN('Available Months'[Month Start])."""
        return self.month_starts[0]

    @property
    def max_month_start(self) -> pd.Timestamp:
        """MAX('Available Months'[Month Start])."""
        return self.month_starts[-1]

    @property
    def max_month_end(self) -> pd.Timestamp:
        """EOMONTH(MAX('Available Months'[Month Start]), 0)."""
        return self.max_month_start + pd.offsets.MonthEnd(0)


def build_available_months(df: pd.DataFrame) -> AvailableMonths:
    """
    Derive the `Available Months` (+ `Calendar[Date]` MIN) date dimension
    from the roster data. See module docstring for the exact boundary
    logic and its rationale.

    Reads: `DOJ (DEPT)`, `LWD`, `Today`.
    Edge cases: rows with unparseable `DOJ (DEPT)`/`LWD` (NaT after
    coercion) are excluded from the min/max computation, not treated as
    an arbitrary boundary.
    Raises: ValueError if no row has a parseable `DOJ (DEPT)` (can't
    derive a calendar with no valid dates at all).
    """
    doj = pd.to_datetime(df["DOJ (DEPT)"], format=DATE_FORMAT, errors="coerce")
    lwd = pd.to_datetime(df["LWD"], format=DATE_FORMAT, errors="coerce")
    today = pd.to_datetime(df["Today"], format=DATE_FORMAT, errors="coerce")

    if doj.notna().sum() == 0:
        # An EMPTY calendar, not an error. Filtering is applied server-side
        # now, so a legitimate filter combination can select zero rows (or
        # rows with no joining date) — a user picking "Skill = X" that
        # nobody has must get empty charts, not a 500. Downstream date
        # measures see no months and correctly return zero.
        logger.info(
            "build_available_months: no parseable 'DOJ (DEPT)' in %d row(s) — "
            "returning an empty calendar",
            len(df),
        )
        return AvailableMonths(month_starts=[], earliest_date=None, latest_date=None)

    earliest_date = doj.min()

    latest_candidates = [today.max(), doj.max(), lwd.max()]
    latest_date = max(c for c in latest_candidates if pd.notna(c))

    month_starts: list[pd.Timestamp] = []
    cursor = earliest_date.replace(day=1)
    end_cursor = latest_date.replace(day=1)
    while cursor <= end_cursor:
        month_starts.append(cursor)
        cursor = cursor + pd.offsets.MonthBegin(1)

    return AvailableMonths(
        month_starts=month_starts,
        earliest_date=earliest_date,
        latest_date=latest_date,
    )
