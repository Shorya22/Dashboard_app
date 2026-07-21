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

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture
def real_roster() -> pd.DataFrame:
    return load_roster(DEFAULT_ROSTER_PATH)


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


def test_invariant_fails_loudly_on_an_unaccounted_status(real_roster):
    """
    A Status value no bucket counts must be caught — otherwise those
    employees silently vanish from the Status Split donut.
    """
    df = real_roster.copy()
    df.loc[df.index[0], "Status"] = "Sabbatical"
    bad = {r.name for r in metric_invariants.violations(df, "roster")}
    assert "status_split_sums_to_total" in bad
    assert "status_measures_partition_roster" in bad
