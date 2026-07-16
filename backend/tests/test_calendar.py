"""
Tests for backend/app/services/calendar.py — the derived `Available
Months` / `Calendar[Date]` stand-in used to default period-scoped roster
measures to the full dataset date range.
"""

from __future__ import annotations

import pandas as pd
import pytest

from app.services.calendar import build_available_months


def _row(doj_dept, lwd, today):
    return {"DOJ (DEPT)": doj_dept, "LWD": lwd, "Today": today}


def test_build_available_months_basic_range():
    # DOJ (DEPT) spans Jan 2025 -> Jun 2026; Today is Jun 2026; LWD max
    # is also within Jun 2026 -> expect month_starts Jan 2025..Jun 2026
    # (18 months), earliest_date = 2025-01-01, latest_date = 2026-06-26.
    df = pd.DataFrame(
        [
            _row("1-Jan-25", None, "26-Jun-26"),
            _row("15-Jun-26", "10-Jun-26", "26-Jun-26"),
        ]
    )
    result = build_available_months(df)
    assert result.min_month_start == pd.Timestamp("2025-01-01")
    assert result.max_month_start == pd.Timestamp("2026-06-01")
    assert result.max_month_end == pd.Timestamp("2026-06-30")
    assert result.earliest_date == pd.Timestamp("2025-01-01")
    assert result.latest_date == pd.Timestamp("2026-06-26")
    assert len(result.month_starts) == 18  # Jan25..Jun26 inclusive
    assert result.month_starts[0] == pd.Timestamp("2025-01-01")
    assert result.month_starts[-1] == pd.Timestamp("2026-06-01")


def test_build_available_months_latest_uses_max_of_today_doj_lwd():
    # LWD max (2026-08-01) is later than Today (2026-06-26) and later
    # than max DOJ (DEPT) -> latest_date/month must extend to cover it,
    # not truncate at Today.
    df = pd.DataFrame(
        [
            _row("1-Jan-25", None, "26-Jun-26"),
            _row("1-Feb-25", "1-Aug-26", "26-Jun-26"),
        ]
    )
    result = build_available_months(df)
    assert result.latest_date == pd.Timestamp("2026-08-01")
    assert result.max_month_start == pd.Timestamp("2026-08-01")
    assert result.max_month_end == pd.Timestamp("2026-08-31")


def test_build_available_months_ignores_unparseable_doj():
    # A literal "TBD" DOJ (DEPT) value (confirmed present in the real
    # roster file) must not become an arbitrary boundary -- it's coerced
    # to NaT and excluded from the min/max.
    df = pd.DataFrame(
        [
            _row("TBD", None, "26-Jun-26"),
            _row("1-Jan-25", None, "26-Jun-26"),
        ]
    )
    result = build_available_months(df)
    assert result.earliest_date == pd.Timestamp("2025-01-01")


def test_build_available_months_raises_if_no_valid_doj():
    df = pd.DataFrame([_row("TBD", None, "26-Jun-26")])
    with pytest.raises(ValueError):
        build_available_months(df)
