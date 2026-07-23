"""
Tests for the metric-config self-validation.

The metric config is hand-edited, so a typo is likely. Without validation a
mistake surfaced as a KeyError mid-request — a 500 for whoever happened to
open that page, with a stack trace instead of an explanation. These assert
each mistake is caught when the config loads, and that the message names
the specific thing to fix.
"""

from __future__ import annotations

import copy

import pytest

from app.services import metric_config


@pytest.fixture
def cfg() -> dict:
    return copy.deepcopy(metric_config.load_metric_config())


def test_the_real_config_is_valid():
    metric_config.validate_metric_config(metric_config.load_metric_config())


@pytest.mark.parametrize(
    "label,mutate,expected_in_message",
    [
        (
            "card column_role typo",
            lambda c: c["cards"]["projects"].__setitem__("column_role", "clientt"),
            "clientt",
        ),
        (
            "chart column_role typo",
            lambda c: c["charts"]["headcount_by_region"].__setitem__(
                "column_role", "nope"
            ),
            "nope",
        ),
        (
            "unimplemented chart type",
            lambda c: c["charts"]["status_split"].__setitem__("type", "pie_chart"),
            "pie_chart",
        ),
        (
            "unsupported scope",
            lambda c: c["charts"]["status_split"].__setitem__("scope", "everyone"),
            "everyone",
        ),
        (
            "status_filter naming no declared status",
            lambda c: c["cards"]["active_employees"].__setitem__(
                "status_filter", "activ"
            ),
            "activ",
        ),
        (
            "counts_as_present naming an undeclared status",
            lambda c: c["status"].__setitem__(
                "counts_as_present", ["Active", "Sabbatical"]
            ),
            "Sabbatical",
        ),
        (
            "filter deriving from a chart that doesn't exist",
            lambda c: c["filters"]["experience"].__setitem__(
                "derived_from_chart", "nope"
            ),
            "nope",
        ),
    ],
)
def test_config_mistakes_are_caught_at_load(cfg, label, mutate, expected_in_message):
    mutate(cfg)
    with pytest.raises(metric_config.MetricConfigError) as err:
        metric_config.validate_metric_config(cfg)
    assert expected_in_message in str(err.value), label


def test_last_band_must_be_the_catch_all(cfg):
    """
    Every band except the last declares a `below`. If the last one also had
    one, values above the final threshold would fall into no band at all and
    vanish from the chart.
    """
    cfg["charts"]["workforce_by_experience_band"]["bands"][-1]["below"] = 99
    with pytest.raises(metric_config.MetricConfigError, match="last band"):
        metric_config.validate_metric_config(cfg)


def test_monthly_series_needs_exactly_one_source(cfg):
    """A series is either a measure or a date column — never both, never neither."""
    cfg["charts"]["month_wise_headcount"]["series"][0] = {"key": "x"}
    with pytest.raises(metric_config.MetricConfigError, match="exactly one"):
        metric_config.validate_metric_config(cfg)

    cfg["charts"]["month_wise_headcount"]["series"][0] = {
        "key": "x",
        "measure": "closing_headcount",
        "date_role": "joining_date",
    }
    with pytest.raises(metric_config.MetricConfigError, match="exactly one"):
        metric_config.validate_metric_config(cfg)


def test_unimplemented_measure_is_caught(cfg):
    cfg["charts"]["month_wise_headcount"]["series"][0]["measure"] = "made_up"
    with pytest.raises(metric_config.MetricConfigError, match="made_up"):
        metric_config.validate_metric_config(cfg)


def test_crosstab_dimension_cannot_drift_from_the_standalone_chart():
    """
    'Skill Bifurcation by Experience' buckets experience by reusing the
    standalone experience chart's bands (dimension_from_chart), so the two
    are the same definition. Changing the bands in one place must move
    both — the whole reason the separate Python `_experience_band` copy was
    removed.
    """
    import copy

    import yaml

    from app.services import roster_metrics
    from app.services.roster_metrics import load_roster
    from app.services.validation.engine import prepare_dataset

    df = prepare_dataset(
        load_roster(
            __import__("pathlib").Path(__file__).resolve().parent
            / "fixtures"
            / "roster_snapshot.xlsx"
        ),
        "roster",
    )

    original = copy.deepcopy(metric_config.load_metric_config())
    cfg_path = (
        __import__("pathlib").Path(metric_config.__file__).resolve().parent
        / "configs"
        / "roster_metrics.yaml"
    )
    backup = cfg_path.read_text()
    try:
        cfg = yaml.safe_load(backup)
        cfg["charts"]["workforce_by_experience_band"]["bands"] = [
            {"below": 5, "label": "Junior"},
            {"label": "Senior"},
        ]
        cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False))
        metric_config.load_metric_config.cache_clear()

        standalone = set(roster_metrics.get_workforce_by_experience_band(df))
        crosstab = {
            r["experience_band"]
            for r in roster_metrics.get_skill_bifurcation_by_experience_band(df)
        }
        assert standalone == {"Junior", "Senior"}
        assert crosstab <= {"Junior", "Senior"}  # same bands, no old labels
    finally:
        cfg_path.write_text(backup)
        metric_config.load_metric_config.cache_clear()
        assert metric_config.load_metric_config() == original
