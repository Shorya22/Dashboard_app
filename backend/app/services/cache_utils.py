"""
Small in-process caching helper for aggregation results computed from a
cached DataFrame (see `data_loader.py`).

Why this exists / caching-key strategy:
- `data_loader.py` already loads each source Excel file once and caches
  the resulting DataFrame as a module-level object, only replacing it
  when `reload_*()` is called explicitly.
- Many `services/` aggregation functions are pure functions of that
  DataFrame (plus, at most, a few small hashable arguments like
  `employee` or `holding`) — calling them again with the *same*
  DataFrame object produces the *same* result every time, but they were
  being recomputed (groupby/aggregate from scratch) on every single API
  request.
- `functools.lru_cache` can't be used directly on these functions
  because a `pandas.DataFrame` isn't hashable. Instead, `cache_on_df`
  below keys its cache on `id(df)` (the DataFrame's object identity)
  plus any other call arguments. Since `data_loader` only ever swaps in
  a *new* DataFrame object on `reload_*()`, `id(df)` changes exactly
  when the underlying data changes — old cache entries simply become
  unreachable (never returned again) after a reload. This gives cache
  invalidation "for free", tied to the existing reload pattern, with no
  extra bookkeeping (no version counters, no manual `cache_clear()`
  calls needed on reload).
- Trade-off accepted for this app's scale (three DataFrames, reloaded
  rarely, single process): stale entries from a since-replaced
  DataFrame stay in the dict (and keep that old DataFrame alive) until
  process restart — a small, bounded memory cost, never a correctness
  problem, since they're never looked up again by the new object's id.
  Not worth a weakref/LRU eviction scheme at this data size.
"""

from __future__ import annotations

import functools
import threading
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


def cache_on_df(fn: F) -> F:
    """
    Cache `fn`'s return value keyed on `(id(first_arg), *rest, **kwargs)`.

    Intended for `services/` functions whose first positional argument is
    the cached DataFrame (`df`, `booking_df`, `ground_truth_long_df`,
    ...) and whose remaining arguments (if any) are small and hashable
    (e.g. `employee: str`). Do not use on functions taking unhashable
    extra arguments (e.g. raw lists) without converting them to tuples
    first.
    """
    # Each entry stores (df_reference, result). Keeping a strong reference
    # to the DataFrame alongside its cached result is required for
    # correctness, not just a memory nicety: `id()` is only guaranteed
    # unique among *currently alive* objects. If a DataFrame were allowed
    # to be garbage-collected while its id() is still a cache key, Python
    # can (and, empirically, quickly does — e.g. across pytest fixtures
    # that build many short-lived small DataFrames) reuse that same
    # address for an unrelated new DataFrame, which would then silently
    # hit a stale cache entry belonging to different data. Storing the
    # reference keeps the object alive for as long as its cache entry
    # exists, so its id() can never be recycled out from under us; the
    # `cached_df is df` check on lookup is a second, explicit guard
    # against exactly that hazard.
    cache: dict[tuple, tuple[Any, Any]] = {}
    lock = threading.Lock()

    @functools.wraps(fn)
    def wrapper(df, *args: Any, **kwargs: Any) -> Any:
        key = (id(df), args, tuple(sorted(kwargs.items())))
        with lock:
            entry = cache.get(key)
            if entry is not None and entry[0] is df:
                return entry[1]
        result = fn(df, *args, **kwargs)
        with lock:
            cache[key] = (df, result)
        return result

    def cache_clear() -> None:
        with lock:
            cache.clear()

    wrapper.cache_clear = cache_clear  # type: ignore[attr-defined]
    return wrapper  # type: ignore[return-value]
