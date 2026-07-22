"""
Tests for the metric invariants (app/services/metric_invariants.py).

These guard a bug class rather than a single bug: two functions each
computing the same business concept, rendered under the same label on
different pages, drifting apart when the data changes. That is exactly
what happened with Strategic Pool (Home showed 1, HR Home showed 3).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.services import metric_invariants, roster_metrics
from app.services.roster_metrics import DEFAULT_ROSTER_PATH, load_roster

# Frozen snapshots — invariants must hold for LOGIC reasons, so they are
# checked against stable data rather than the live files (which change with
# every business upload).
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def real_roster() -> pd.DataFrame:
    from app.services.validation.engine import apply_dataset_defaults

    return apply_dataset_defaults(
        load_roster(FIXTURES_DIR / "roster_snapshot.xlsx"), "roster"
    )


def test_real_roster_satisfies_all_invariants(real_roster):
    bad = metric_invariants.violations(real_roster, "roster")
    assert bad == [], [f"{r.name}: {r.detail}" for r in bad]


def test_every_invariant_actually_ran(real_roster):
    results = metric_invariants.run_invariants(real_roster, "roster")
    assert {r.name for r in results} == set(metric_invariants.ROSTER_INVARIANTS)


def test_strategic_pool_is_status_based_everywhere(real_roster):
    """
    The regression this whole module exists for: Strategic Pool must be
    the same number wherever it is surfaced.
    """
    canonical = roster_metrics.get_strategic_pool(real_roster)
    assert roster_metrics.get_status_split(real_roster)["Strategic Pool"] == canonical
    assert (
        roster_metrics.get_workforce_category_split(real_roster)["Strategic Pool"]
        == canonical
    )
    # ...and it is the Status marker, not a blank DOJ (DEPT) proxy.
    expected = int((real_roster["Status"] == "Strategic Pool").sum())
    assert canonical == expected


def test_invariant_catches_the_original_divergence(real_roster):
    """
    Reproduce the shape of the roster that broke it: an employee marked
    Strategic Pool who has a perfectly good DOJ (DEPT). Under the old
    blank-DOJ definition the two donuts disagreed; the invariant must
    hold now, proving the definitions are genuinely unified.
    """
    df = real_roster.copy()
    active_idx = df.index[df["Status"] == "Active"][0]
    df.loc[active_idx, "Status"] = "Strategic Pool"  # DOJ (DEPT) left intact
    assert metric_invariants.violations(df, "roster") == []
    assert roster_metrics.get_strategic_pool(df) == int(
        (df["Status"] == "Strategic Pool").sum()
    )


def test_booking_hours_split_covers_all_hours():
    """Client + Internal must account for every booked hour."""
    from app.services.roster_metrics import load_roster  # noqa: F401  (path style)
    from app.services.booking_metrics import load_booking_data

    df = load_booking_data(FIXTURES_DIR / "booking_snapshot.xlsx")
    assert metric_invariants.violations(df, "booking") == []


def test_booking_invariant_catches_a_new_hours_category():
    """
    A category the donut doesn't know about (e.g. "Leave Hours") would
    still count toward total hours but appear in neither slice, quietly
    under-reporting. That must be flagged, and the culprit named.
    """
    from app.services.booking_metrics import load_booking_data

    df = load_booking_data(FIXTURES_DIR / "booking_snapshot.xlsx").copy()
    df.loc[df.index[:40], "Booked Hours Type"] = "Leave Hours"
    bad = metric_invariants.violations(df, "booking")
    assert [r.name for r in bad] == ["hours_split_covers_all_hours"]
    assert "Leave Hours" in bad[0].detail


def test_undeclared_status_is_shown_but_still_flagged(real_roster):
    """
    An unrecognised Status no longer vanishes from the donut — it renders
    as its own slice, so nobody is lost. It is still a config gap though:
    nothing has decided whether those people count as present, so they sit
    outside Closing Headcount while counting in Total Employees. Both
    facts are asserted here.
    """
    from app.services import roster_metrics

    df = real_roster.copy()
    df.loc[df.index[0], "Status"] = "Sabbatical"

    split = roster_metrics.get_status_split(df)
    assert split["Sabbatical"] == 1                      # shown, not dropped
    assert sum(split.values()) == roster_metrics.get_total_employees(df)

    bad = {r.name for r in metric_invariants.violations(df, "roster")}
    assert "every_status_is_declared" in bad             # config gap surfaced
    assert "status_measures_partition_roster" in bad


def test_blank_group_by_values_are_labelled_not_dropped(real_roster):
    """
    A blank Region used to be dropped by the group-by, so the bars totalled
    less than the headline card with nothing on screen to explain the gap.
    """
    from app.services import roster_metrics

    df = real_roster.copy()
    df.loc[df.index[:4], "Region"] = None
    df.loc[df.index[5:8], "Working Entity"] = None

    total = roster_metrics.get_total_employees(df)
    regions = roster_metrics.get_headcount_by_region(df)
    entities = roster_metrics.get_workforce_by_working_entity(df)

    assert regions["Region TBD"] >= 4
    assert entities["Entity TBD"] >= 3
    assert sum(regions.values()) == total
    assert sum(entities.values()) == total
    assert metric_invariants.violations(df, "roster") == []
