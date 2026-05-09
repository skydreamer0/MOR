"""Taiwan workday calendar service.

Fetches the official Taiwan government office-day data from the ruyut/TaiwanCalendar
CDN (which aggregates Directorate-General of Personnel Administration data) and stores
it in the workday_calendar table.  All public calculation helpers fall back to Mon–Fri
when DB data is absent for the requested date range.
"""
from __future__ import annotations

import calendar
import json
import urllib.request
from datetime import date, timedelta
from typing import Iterable

from src.backend.database import MORDatabase


_CALENDAR_URL = "https://cdn.jsdelivr.net/gh/ruyut/TaiwanCalendar/data/{year}.json"
_SOURCE_LABEL = "ruyut/TaiwanCalendar"


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------

def sync_taiwan_calendar(db: MORDatabase, year: int, timeout: int = 10) -> int:
    """Fetch official Taiwan calendar for *year* and upsert into workday_calendar.

    Returns the number of rows upserted.  Raises on network or parse failure so
    the caller can decide whether to fall back silently.
    """
    url = _CALENDAR_URL.format(year=year)
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        entries = json.loads(resp.read().decode("utf-8"))

    rows = []
    for entry in entries:
        raw_date = str(entry.get("date", ""))
        if len(raw_date) != 8:
            continue
        iso_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
        is_workday = 0 if entry.get("isHoliday", False) else 1
        holiday_name = entry.get("description", "") or None
        rows.append((iso_date, is_workday, holiday_name, _SOURCE_LABEL, None))

    if not rows:
        raise ValueError(f"台灣工作日曆資料為空：{url}")

    with db.get_connection() as conn:
        conn.executemany(
            """
            INSERT INTO workday_calendar (date, is_workday, holiday_name, source, note)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                is_workday   = excluded.is_workday,
                holiday_name = excluded.holiday_name,
                source       = excluded.source,
                note         = excluded.note
            """,
            rows,
        )
        conn.commit()
    return len(rows)


def ensure_calendar_year(db: MORDatabase, year: int) -> None:
    """Sync *year* if the DB has no data for it yet (silent fallback on failure)."""
    with db.get_connection() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM workday_calendar WHERE date LIKE ?",
            (f"{year}-%",),
        ).fetchone()[0]
    if count == 0:
        try:
            sync_taiwan_calendar(db, year)
        except Exception:
            pass  # Fallback to Mon–Fri will activate automatically in the calculation helpers


# ---------------------------------------------------------------------------
# Calculation helpers
# ---------------------------------------------------------------------------

def is_workday(db: MORDatabase, d: date) -> bool:
    """Return True if *d* is a workday according to DB; falls back to Mon–Fri."""
    iso = d.isoformat()
    with db.get_connection() as conn:
        row = conn.execute(
            "SELECT is_workday FROM workday_calendar WHERE date = ?", (iso,)
        ).fetchone()
    if row is not None:
        return bool(row["is_workday"])
    # Fallback: Mon–Fri
    return d.weekday() < 5


def count_workdays(db: MORDatabase, start: date, end: date) -> int:
    """Count workdays in [start, end] inclusive."""
    if start > end:
        return 0
    iso_start, iso_end = start.isoformat(), end.isoformat()
    with db.get_connection() as conn:
        db_count = conn.execute(
            """
            SELECT COUNT(*) FROM workday_calendar
            WHERE date >= ? AND date <= ? AND is_workday = 1
            """,
            (iso_start, iso_end),
        ).fetchone()[0]
        total_in_db = conn.execute(
            "SELECT COUNT(*) FROM workday_calendar WHERE date >= ? AND date <= ?",
            (iso_start, iso_end),
        ).fetchone()[0]

    total_days = (end - start).days + 1
    if total_in_db >= total_days:
        # Full coverage in DB
        return db_count

    # Partial or no coverage — fall back to Mon–Fri for all days in range
    return sum(1 for i in range(total_days) if (start + timedelta(days=i)).weekday() < 5)


def workdays_elapsed_in_month(db: MORDatabase, year: int, month: int, as_of: date) -> int:
    """Count workdays from month start up to and including *as_of*."""
    month_start = date(year, month, 1)
    cutoff = min(as_of, _month_end(year, month))
    if cutoff < month_start:
        return 0
    return count_workdays(db, month_start, cutoff)


def total_workdays_in_month(db: MORDatabase, year: int, month: int) -> int:
    """Count total workdays in the given month."""
    return count_workdays(db, date(year, month, 1), _month_end(year, month))


def workdays_remaining_in_month(db: MORDatabase, year: int, month: int, as_of: date) -> int:
    """Count workdays from the day after *as_of* to month end (inclusive)."""
    next_day = as_of + timedelta(days=1)
    month_end = _month_end(year, month)
    if next_day > month_end:
        return 0
    return count_workdays(db, next_day, month_end)


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _month_end(year: int, month: int) -> date:
    _, last = calendar.monthrange(year, month)
    return date(year, month, last)
