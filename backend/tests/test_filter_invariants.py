"""Cross-filter invariants that must hold for EVERY declared filter on
EVERY dataset. These aren't per-filter tests — they lock in properties
the filter model as a whole promises, so a filter added later can't
silently break them.

Current invariant:

  "Selecting every option a filter can offer must return the same
  result set as selecting nothing at all."

  In UI terms: ticking every checkbox in a dropdown is indistinguishable
  from clearing the dropdown. Regression: HR Analytics' Month/Year
  filter was dropping rows with unparseable DOJ (e.g. Rahul Malhotra,
  DOJ literal "TBD", Strategic Pool) — so `Total Employees` read 52
  when the filter was empty but 51 when every year was ticked. Fixed
  by treating blank DOJ as satisfying the DAX `<=` comparison, matching
  `get_closing_headcount`'s already-established BLANK() parity rule.
"""

from __future__ import annotations

import os
import tempfile

os.environ.setdefault(
    "DATABASE_URL",
    "sqlite:///"
    + tempfile.mktemp(prefix="dashboard_filter_inv_", suffix=".db").replace("\\", "/"),
)

import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from app.services import metric_config, roster_metrics  # noqa: E402
from app.services.data_loader import get_roster_df  # noqa: E402


@pytest.fixture(scope="module")
def roster() -> pd.DataFrame:
    return get_roster_df()


def _all_option_values(df: pd.DataFrame, spec: dict) -> list[str]:
    """Every value the frontend could show in the filter's dropdown.

    Time filters (`time_filter: true`) are month labels — the exact
    set the roster trend endpoint would emit. Chart-derived filters
    reuse the chart's own bucket labels. Plain column filters use the
    column's distinct values.
    """
    if spec.get("time_filter"):
        # Same list `_evaluate_monthly_series` walks — the frontend's
        # dropdown is built from this via `monthsToHierarchy`.
        from app.services.calendar import build_available_months

        available = build_available_months(df)
        return [m.strftime("%b %Y") for m in available.month_starts]

    chart = spec.get("derived_from_chart")
    if chart:
        labels = roster_metrics.chart_labels(df, metric_config.chart(chart))
        return sorted(labels.astype(str).unique())

    column = metric_config.column(spec["column_role"])
    return sorted(df[column].dropna().astype(str).unique())


def test_selecting_all_options_matches_no_filter_for_every_roster_filter(roster):
    """The invariant: for every roster filter, passing every option the
    user could tick equals passing none at all — the "cleared vs
    fully-ticked" dropdown must be visually the same result set. Loops
    over `metric_config.filters()` so a new filter added tomorrow is
    checked automatically, without editing this test file."""
    baseline = roster_metrics.apply_filters(roster, {})
    baseline_ids = set(baseline.index)

    for name, spec in metric_config.filters().items():
        options = _all_option_values(roster, spec)
        if not options:
            # No options in the fixture — skip rather than testing a
            # trivially-empty selection.
            continue
        result = roster_metrics.apply_filters(roster, {name: options})
        result_ids = set(result.index)
        assert result_ids == baseline_ids, (
            f"filter {name!r}: ticking every option ({len(options)}) "
            f"returned {len(result_ids)} rows, but no filter returned "
            f"{len(baseline_ids)}. Missing from all-selected: "
            f"{sorted(baseline_ids - result_ids)}; extra: "
            f"{sorted(result_ids - baseline_ids)}"
        )
