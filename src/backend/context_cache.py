"""ContextCache — version-based cache invalidation for forecast page contexts.

Wraps Flask-Caching with two version counters so that cache keys change on
writes without requiring explicit cache.delete() calls:

  _global_version  — incremented when any month's data could change
                     (Excel sync, item config saves)
  _month_versions  — incremented when a specific month changes
                     (row adjustments, daily imports, close-month)

Cache entries age out only via LRU eviction (CACHE_THRESHOLD) since
CACHE_DEFAULT_TIMEOUT=0 (no TTL). Old versioned keys become unreachable
and are evicted naturally.
"""
from __future__ import annotations

from datetime import date
from typing import Callable, TypeVar

T = TypeVar("T")


class ContextCache:
    def __init__(self, flask_cache) -> None:
        self._cache = flask_cache
        self._month_versions: dict[tuple[int, int], int] = {}
        self._global_version: int = 0

    def make_key(self, year: int, month: int, as_of: date | None = None) -> str:
        key = (
            f"forecast-context:{year}:{month}"
            f":g{self._global_version}"
            f":m{self._month_versions.get((year, month), 0)}"
        )
        if as_of is not None:
            key += f":d{as_of.isoformat()}"
        return key

    def invalidate(self, year: int, month: int) -> None:
        """Bump the per-month version so the next request rebuilds that month."""
        self._month_versions[(year, month)] = self._month_versions.get((year, month), 0) + 1

    def invalidate_all(self) -> None:
        """Bump the global version so the next request rebuilds every month."""
        self._global_version += 1

    def get_or_build(
        self,
        year: int,
        month: int,
        builder: Callable[[], T],
        *,
        today: date | None = None,
    ) -> T:
        """Return cached context for (year, month), or call builder() and cache it.

        For the current calendar month the cache key includes today's date so
        that intra-day updates (daily imports) land in the right slot.
        """
        context_today = today or date.today()
        as_of = context_today if (year, month) == (context_today.year, context_today.month) else None
        key = self.make_key(year, month, as_of)
        cached = self._cache.get(key)
        if cached is None:
            cached = builder()
            self._cache.set(key, cached)
        return cached
