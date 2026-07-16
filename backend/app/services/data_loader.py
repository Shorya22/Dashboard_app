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
                _roster_cache = load_roster()
    return _roster_cache


def get_booking_df() -> pd.DataFrame:
    """Return the cached booking DataFrame, loading it on first use."""
    global _booking_cache
    if _booking_cache is None:
        with _load_lock:
            if _booking_cache is None:
                _booking_cache = load_booking_data()
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


def get_utilization_ground_truth_df() -> pd.DataFrame:
    """Return the cached `Utilization_Long` ground-truth DataFrame, loading it on first use."""
    global _utilization_ground_truth_cache
    if _utilization_ground_truth_cache is None:
        with _load_lock:
            if _utilization_ground_truth_cache is None:
                _utilization_ground_truth_cache = load_ground_truth_long()
    return _utilization_ground_truth_cache


def reload_roster() -> pd.DataFrame:
    """Force a re-read of the roster Excel file, refreshing the cache."""
    global _roster_cache
    with _load_lock:
        _roster_cache = load_roster()
    logger.info("reload_roster: cache refreshed")
    return _roster_cache


def reload_booking_data() -> pd.DataFrame:
    """Force a re-read of the booking Excel file, refreshing the cache."""
    global _booking_cache, _booking_prepared_cache
    with _load_lock:
        _booking_cache = load_booking_data()
        _booking_prepared_cache = None  # recomputed lazily from the new df
    logger.info("reload_booking_data: cache refreshed")
    return _booking_cache


def reload_utilization_ground_truth() -> pd.DataFrame:
    """Force a re-read of the utilization ground-truth Excel file, refreshing the cache."""
    global _utilization_ground_truth_cache
    with _load_lock:
        _utilization_ground_truth_cache = load_ground_truth_long()
    logger.info("reload_utilization_ground_truth: cache refreshed")
    return _utilization_ground_truth_cache
