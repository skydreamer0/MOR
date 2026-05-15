"""Tests for workday_calendar — no network calls; all calendar data injected directly."""
from datetime import date
from pathlib import Path

import pytest

from src.backend.database import MORDatabase
from src.backend.workday_calendar import (
    count_workdays,
    is_workday,
    sync_taiwan_calendar,
    total_workdays_in_month,
    workdays_elapsed_in_month,
    workdays_remaining_in_month,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _db(tmp_path: Path) -> MORDatabase:
    return MORDatabase(tmp_path / "mor_workbench.db")


def _insert_days(db: MORDatabase, entries: list[tuple[str, int, str | None]]) -> None:
    """entries: (iso_date, is_workday, holiday_name)"""
    with db.get_connection() as conn:
        conn.executemany(
            "INSERT INTO workday_calendar (date, is_workday, holiday_name, source) VALUES (?, ?, ?, 'test')",
            entries,
        )
        conn.commit()


def _may_2026(db: MORDatabase) -> None:
    """Insert a realistic 2026-05 calendar (公曆假日 + 補班 already handled).

    2026-05:
      - Mon 04 → workday
      - Sat 02, Sun 03, Sat 09, Sun 10 → holiday (weekend)
      - Thu 07 → workday
      - ...
    We just insert all 31 days with Mon–Fri = workday, Sat/Sun = holiday,
    no special holidays in May 2026 per standard calendar.
    """
    from datetime import timedelta
    rows = []
    d = date(2026, 5, 1)
    while d.month == 5:
        is_wd = 0 if d.weekday() >= 5 else 1
        rows.append((d.isoformat(), is_wd, None))
        d += timedelta(days=1)
    _insert_days(db, rows)


# ---------------------------------------------------------------------------
# DB schema
# ---------------------------------------------------------------------------

def test_workday_calendar_table_exists(tmp_path: Path):
    db = _db(tmp_path)
    with db.get_connection() as conn:
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(workday_calendar)").fetchall()}
    assert {"date", "is_workday", "holiday_name", "source", "note"}.issubset(cols)


# ---------------------------------------------------------------------------
# is_workday — DB lookup and Mon–Fri fallback
# ---------------------------------------------------------------------------

def test_is_workday_returns_db_value(tmp_path: Path):
    db = _db(tmp_path)
    # 2026-05-01 is Friday — mark it as holiday (勞動節)
    _insert_days(db, [("2026-05-01", 0, "勞動節")])
    assert is_workday(db, date(2026, 5, 1)) is False


def test_is_workday_falls_back_to_mon_fri_when_no_db_data(tmp_path: Path):
    db = _db(tmp_path)  # empty calendar
    assert is_workday(db, date(2026, 5, 4)) is True   # Monday
    assert is_workday(db, date(2026, 5, 9)) is False  # Saturday


# ---------------------------------------------------------------------------
# count_workdays
# ---------------------------------------------------------------------------

def test_count_workdays_uses_db_when_coverage_is_complete(tmp_path: Path):
    db = _db(tmp_path)
    _may_2026(db)
    # 2026-05-04 (Mon) to 2026-05-08 (Fri) → 5 workdays
    assert count_workdays(db, date(2026, 5, 4), date(2026, 5, 8)) == 5


def test_count_workdays_excludes_holiday_in_db(tmp_path: Path):
    db = _db(tmp_path)
    _may_2026(db)
    # Mark 2026-05-07 (Thu) as holiday
    with db.get_connection() as conn:
        conn.execute("UPDATE workday_calendar SET is_workday = 0 WHERE date = '2026-05-07'")
        conn.commit()
    # Mon–Fri week minus Thu = 4 workdays
    assert count_workdays(db, date(2026, 5, 4), date(2026, 5, 8)) == 4


def test_count_workdays_falls_back_to_mon_fri_for_empty_db(tmp_path: Path):
    db = _db(tmp_path)  # no calendar data
    # 2026-05-04 (Mon) to 2026-05-10 (Sun): Mon–Fri = 5 workdays
    assert count_workdays(db, date(2026, 5, 4), date(2026, 5, 10)) == 5


def test_count_workdays_returns_zero_for_inverted_range(tmp_path: Path):
    db = _db(tmp_path)
    assert count_workdays(db, date(2026, 5, 10), date(2026, 5, 4)) == 0


# ---------------------------------------------------------------------------
# total_workdays_in_month
# ---------------------------------------------------------------------------

def test_total_workdays_in_month_may_2026(tmp_path: Path):
    db = _db(tmp_path)
    _may_2026(db)
    # May 2026: 31 days, weekends = Sat/Sun
    # Week 1: Fri 01 = workday (1), Sat 02, Sun 03 = off
    # Week 2: Mon 04–Fri 08 = 5 workdays
    # Week 3: Mon 11–Fri 15 = 5 workdays
    # Week 4: Mon 18–Fri 22 = 5 workdays
    # Week 5: Mon 25–Fri 29 = 5 workdays
    # Week 6: Sat 30, Sun 31 = off
    # Total = 1 + 5 + 5 + 5 + 5 = 21
    assert total_workdays_in_month(db, 2026, 5) == 21


def test_total_workdays_in_month_fallback_when_no_db(tmp_path: Path):
    db = _db(tmp_path)
    # Fallback: same Mon–Fri count = 21
    assert total_workdays_in_month(db, 2026, 5) == 21


# ---------------------------------------------------------------------------
# workdays_elapsed_in_month
# ---------------------------------------------------------------------------

def test_workdays_elapsed_counts_from_month_start(tmp_path: Path):
    db = _db(tmp_path)
    _may_2026(db)
    # Up to and including 2026-05-08 (Fri): Fri 01 + Mon–Fri 04-08 = 6 workdays
    assert workdays_elapsed_in_month(db, 2026, 5, date(2026, 5, 8)) == 6


def test_workdays_elapsed_before_month_start_returns_zero(tmp_path: Path):
    db = _db(tmp_path)
    _may_2026(db)
    assert workdays_elapsed_in_month(db, 2026, 5, date(2026, 4, 30)) == 0


def test_workdays_elapsed_clamps_to_month_end(tmp_path: Path):
    db = _db(tmp_path)
    _may_2026(db)
    # Passing a date beyond May should return full month count
    assert workdays_elapsed_in_month(db, 2026, 5, date(2026, 6, 15)) == 21


# ---------------------------------------------------------------------------
# workdays_remaining_in_month
# ---------------------------------------------------------------------------

def test_workdays_remaining_excludes_today(tmp_path: Path):
    db = _db(tmp_path)
    _may_2026(db)
    # As of 2026-05-08 (Fri): remaining = Mon 11 … Fri 29 = 4 × 5 = 15 + Fri 01... no
    # May 2026: total=21, elapsed up to 08 = 6, remaining from 09 = 21 - 6 = 15
    assert workdays_remaining_in_month(db, 2026, 5, date(2026, 5, 8)) == 15


def test_workdays_remaining_at_month_end_is_zero(tmp_path: Path):
    db = _db(tmp_path)
    _may_2026(db)
    assert workdays_remaining_in_month(db, 2026, 5, date(2026, 5, 31)) == 0


# ---------------------------------------------------------------------------
# sync_taiwan_calendar — mock network, verify DB rows
# ---------------------------------------------------------------------------

def test_sync_taiwan_calendar_inserts_and_overwrites(tmp_path: Path, monkeypatch):
    db = _db(tmp_path)

    fake_json = json.dumps(
        [
            {"date": "20260504", "week": "一", "isHoliday": False, "description": ""},
            {"date": "20260509", "week": "六", "isHoliday": True, "description": "週六"},
            {"date": "20260510", "week": "日", "isHoliday": True, "description": "週日"},
        ]
    ).encode("utf-8")

    class _FakeResp:
        def read(self): return fake_json
        def __enter__(self): return self
        def __exit__(self, *_): pass

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **kw: _FakeResp())

    count = sync_taiwan_calendar(db, 2026)

    assert count == 3
    with db.get_connection() as conn:
        rows = {row["date"]: row for row in conn.execute("SELECT * FROM workday_calendar").fetchall()}
    assert rows["2026-05-04"]["is_workday"] == 1
    assert rows["2026-05-09"]["is_workday"] == 0
    assert rows["2026-05-09"]["holiday_name"] == "週六"

    # Overwrite: sync again with updated data
    fake_json2 = json.dumps(
        [{"date": "20260504", "week": "一", "isHoliday": True, "description": "補假"}]
    ).encode("utf-8")

    class _FakeResp2:
        def read(self): return fake_json2
        def __enter__(self): return self
        def __exit__(self, *_): pass

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **kw: _FakeResp2())
    sync_taiwan_calendar(db, 2026)

    with db.get_connection() as conn:
        row = conn.execute("SELECT * FROM workday_calendar WHERE date='2026-05-04'").fetchone()
    assert row["is_workday"] == 0
    assert row["holiday_name"] == "補假"


import json  # noqa: E402 — placed here so the test above can reference it
