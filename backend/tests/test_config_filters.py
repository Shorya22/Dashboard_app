"""Tests for `metric_config.filters(dataset)` and `GET /api/v1/config/filters`.

Filter DEFINITIONS live in YAML for both datasets; VALUES stay data-derived.
These tests pin the YAML→endpoint contract.
"""

from __future__ import annotations

import copy

import pytest

# Import chain matters — test_auth imports first to establish the temp DB
# and seed the dev admin. Reuse its client + login flow here.
from tests.test_auth import client, SEED_EMAIL, SEED_PASSWORD  # noqa: F401

from app.services import metric_config


# --- metric_config.filters(dataset) ----------------------------------------


def test_filters_roster_dataset_returns_expected_keys():
    defs = metric_config.filters("roster")
    for key in ("status", "department", "region", "market", "skill", "type",
                "allocation", "grade", "experience", "seniorityCategory"):
        assert key in defs, key
    assert defs["region"]["nests"] == "market"
    assert defs["region"]["type"] == "multi"


def test_filters_booking_dataset_returns_expected_shape():
    defs = metric_config.filters("booking")
    for key in ("region", "market", "department", "entity", "holding",
                "hours_type", "week"):
        assert key in defs, key
    assert defs["region"]["column_role"] == "region"
    assert defs["region"]["nests"] == "market"
    assert defs["hours_type"]["type"] == "single"
    assert defs["week"]["type"] == "hierarchical"
    assert defs["week"]["label"] == "Month / Week"


def test_filters_default_dataset_is_roster():
    assert metric_config.filters() == metric_config.filters("roster")


def test_booking_columns_helper():
    cols = metric_config.booking_columns()
    assert cols["region"] == "Region (EC)"
    assert cols["hours_type"] == "Booked Hours Type"


# --- validator ------------------------------------------------------------


@pytest.fixture
def booking_cfg() -> dict:
    return copy.deepcopy(metric_config.load_metric_config("booking"))


def test_booking_cfg_validates_clean(booking_cfg):
    metric_config.validate_metric_config(booking_cfg, dataset="booking")


def test_bad_filter_type_is_caught(booking_cfg):
    booking_cfg["filters"]["region"]["type"] = "combobox"
    with pytest.raises(metric_config.MetricConfigError, match="combobox"):
        metric_config.validate_metric_config(booking_cfg, dataset="booking")


def test_nests_pointing_at_missing_filter_is_caught(booking_cfg):
    booking_cfg["filters"]["region"]["nests"] = "not-a-filter"
    with pytest.raises(metric_config.MetricConfigError, match="not-a-filter"):
        metric_config.validate_metric_config(booking_cfg, dataset="booking")


def test_unknown_column_role_in_booking_filter_is_caught(booking_cfg):
    booking_cfg["filters"]["region"]["column_role"] = "nope"
    with pytest.raises(metric_config.MetricConfigError, match="nope"):
        metric_config.validate_metric_config(booking_cfg, dataset="booking")


def test_applies_to_pages_must_be_list_of_strings(booking_cfg):
    booking_cfg["filters"]["region"]["applies_to_pages"] = "utilization-home"
    with pytest.raises(metric_config.MetricConfigError, match="applies_to_pages"):
        metric_config.validate_metric_config(booking_cfg, dataset="booking")


# --- endpoint -------------------------------------------------------------


def _auth_headers(client) -> dict[str, str]:  # noqa: F811
    resp = client.post(
        "/api/auth/login",
        json={"email": SEED_EMAIL, "password": SEED_PASSWORD},
    )
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_config_filters_roster_endpoint(client):  # noqa: F811
    resp = client.get("/api/v1/config/filters?dataset=roster", headers=_auth_headers(client))
    assert resp.status_code == 200
    body = resp.json()
    assert body["dataset"] == "roster"
    keys = {f["key"] for f in body["filters"]}
    assert {"status", "region", "market", "department"}.issubset(keys)
    region = next(f for f in body["filters"] if f["key"] == "region")
    assert region["nests"] == "market"
    assert region["type"] == "multi"
    assert region["label"] == "Region"


def test_config_filters_booking_endpoint(client):  # noqa: F811
    resp = client.get("/api/v1/config/filters?dataset=booking", headers=_auth_headers(client))
    assert resp.status_code == 200
    body = resp.json()
    assert body["dataset"] == "booking"
    keys = {f["key"] for f in body["filters"]}
    assert {"region", "market", "department", "entity", "holding",
            "hours_type", "week"}.issubset(keys)
    week = next(f for f in body["filters"] if f["key"] == "week")
    assert week["type"] == "hierarchical"


def test_config_filters_unknown_dataset_returns_400(client):  # noqa: F811
    resp = client.get(
        "/api/v1/config/filters?dataset=bogus",
        headers=_auth_headers(client),
    )
    assert resp.status_code == 400
    assert "bogus" in resp.json()["detail"]


def test_config_filters_requires_auth(client):  # noqa: F811
    resp = client.get("/api/v1/config/filters?dataset=roster")
    assert resp.status_code == 401
