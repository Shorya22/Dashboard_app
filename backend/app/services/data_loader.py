"""
The ONE place in the app that calls `pandas.read_excel`.

Route handlers and every other module must go through the functions
here (or the FastAPI dependencies below) to get a DataFrame — never
call `load_roster()`/`load_booking_data()` from `roster_metrics.py` /
`booking_metrics.py` directly from a route. This keeps a single seam so
that swapping Excel for a real database later only touches this file.

DataFrames are loaded once per process and cached in-memory (simple
module-level cache) rather than re-read from disk on every request,
per the Phase-2 instructions. Call `reload_*()` to force a re-read
(e.g. useful in tests or if the source file changes on disk).
"""

from __future__ import annotations

import logging
import threading

import pandas as pd

from app.services.booking_metrics import load_booking_data, prepare_booking_df
from app.services.roster_metrics import load_roster
from app.services.utilization_metrics import load_ground_truth_long
from app.services.validation import storage
from app.services.validation.engine import apply_dataset_defaults

logger = logging.getLogger(__name__)

_roster_cache: pd.DataFrame | None = None
_booking_cache: pd.DataFrame | None = None
_booking_prepared_cache: pd.DataFrame | None = None
_utilization_ground_truth_cache: pd.DataFrame | None = None

# Guards the lazy-load-on-first-use path for each cache above, so two
# concurrent requests racing on a cold cache can't both trigger a
# duplicate `pandas.read_excel` (each of which is relatively expensive
# and would otherwise both succeed but do redundant work / briefly waste
# memory on two DataFrame copies before one is discarded). Reads that hit
# an already-populated cache never touch the lock.
_load_lock = threading.Lock()


def get_roster_df() -> pd.DataFrame:
    """Return the cached roster DataFrame, loading it on first use."""
    global _roster_cache
    if _roster_cache is None:
        with _load_lock:
            if _roster_cache is None:  # re-check: lost the race while waiting
                _roster_cache = apply_dataset_defaults(load_roster(storage.resolved_path("roster")), "roster")
    return _roster_cache


def get_booking_df() -> pd.DataFrame:
    """Return the cached booking DataFrame, loading it on first use."""
    global _booking_cache
    if _booking_cache is None:
        with _load_lock:
            if _booking_cache is None:
                _booking_cache = apply_dataset_defaults(load_booking_data(storage.resolved_path("booking")), "booking")
    return _booking_cache


def get_booking_df_prepared() -> pd.DataFrame:
    """
    Return the booking DataFrame with the per-request-repeated cleanup
    (`Monday of Week`/`Date` parsed to datetime, the fully-blank row
    dropped) already applied and cached.

    This used to be redone from scratch — full `.copy()` + `pd.to_datetime`
    over all ~1500 rows — inside `get_filtered_records`/`records_to_dicts`
    on every single `/utilization/records` request regardless of filters.
    Since it depends only on the (rarely-changing) cached booking
    DataFrame, it's computed once here and invalidated the same way as
    every other cache in this module: only on `reload_booking_data()`,
    which builds a new object and so naturally invalidates this too.
    """
    global _booking_prepared_cache
    df = get_booking_df()
    if _booking_prepared_cache is None:
        with _load_lock:
            if _booking_prepared_cache is None:
                _booking_prepared_cache = prepare_booking_df(df)
    return _booking_prepared_cache


def get_utilization_ground_truth_df() -> pd.DataFrame | None:
    """
    Return the cached `Utilization_Long` ground-truth DataFrame, loading it
    on first use, or `None` if the file is not present under
    `backend/data/`.

    As of 2026-07-26 the ground-truth file is OPTIONAL — Overview computes
    from the booking sheet using Formula A (see
    `utilization_metrics.get_utilization_overview`), so a missing
    ground-truth file no longer blocks any runtime endpoint. The QA
    reconcile endpoint (`/api/v1/qa/reconcile`) uses this loader lazily on
    demand and returns 404 if the file is absent.
    """
    global _utilization_ground_truth_cache
    if _utilization_ground_truth_cache is None:
        with _load_lock:
            if _utilization_ground_truth_cache is None:
                raw = load_ground_truth_long(storage.resolved_path("ground_truth"))
                if raw is None:
                    return None
                _utilization_ground_truth_cache = apply_dataset_defaults(raw, "ground_truth")
    return _utilization_ground_truth_cache


def reload_roster() -> pd.DataFrame:
    """Force a re-read of the roster Excel file, refreshing the cache."""
    global _roster_cache
    with _load_lock:
        _roster_cache = apply_dataset_defaults(load_roster(storage.resolved_path("roster")), "roster")
    logger.info("reload_roster: cache refreshed")
    return _roster_cache


def reload_booking_data() -> pd.DataFrame:
    """Force a re-read of the booking Excel file, refreshing the cache."""
    global _booking_cache, _booking_prepared_cache
    with _load_lock:
        _booking_cache = apply_dataset_defaults(load_booking_data(storage.resolved_path("booking")), "booking")
        _booking_prepared_cache = None  # recomputed lazily from the new df
    logger.info("reload_booking_data: cache refreshed")
    return _booking_cache


def reload_utilization_ground_truth() -> pd.DataFrame | None:
    """
    Force a re-read of the utilization ground-truth Excel file, refreshing
    the cache. Returns `None` if the file is absent — the QA reconcile
    endpoint handles that as 404. Runtime endpoints do not call this.
    """
    global _utilization_ground_truth_cache
    with _load_lock:
        raw = load_ground_truth_long(storage.resolved_path("ground_truth"))
        _utilization_ground_truth_cache = (
            apply_dataset_defaults(raw, "ground_truth") if raw is not None else None
        )
    logger.info("reload_utilization_ground_truth: cache refreshed (file %s)", "present" if _utilization_ground_truth_cache is not None else "absent")
    return _utilization_ground_truth_cache
