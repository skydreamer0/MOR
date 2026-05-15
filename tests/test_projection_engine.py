"""Tests for projection_engine — no network calls, all data injected directly."""
from datetime import date, timedelta
from pathlib import Path

import pytest

from src.backend.database import MORDatabase
from src.backend.projection_engine import (
    ProjectionResult,
    _avg_workday_cycle,
    _project,
    _typical_shipment_qty,
    _workdays_between,
    batch_project_eom,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _db(tmp_path: Path) -> MORDatabase:
    return MORDatabase(tmp_path / "mor_workbench.db")


def _workday_set_mondays_only(start: date, end: date) -> frozenset[date]:
    """Simplified: only Mondays are workdays — easy to reason about in tests."""
    result = set()
    d = start
    while d <= end:
        if d.weekday() == 0:  # Monday
            result.add(d)
        d += timedelta(days=1)
    return frozenset(result)


def _mon_fri_set(start: date, end: date) -> frozenset[date]:
    result = set()
    d = start
    while d <= end:
        if d.weekday() < 5:
            result.add(d)
        d += timedelta(days=1)
    return frozenset(result)


# ---------------------------------------------------------------------------
# _workdays_between
# ---------------------------------------------------------------------------

def test_workdays_between_counts_inclusive_end():
    # Mon 2026-05-04 to Fri 2026-05-08: 5 workdays in (Sun 05-03, Fri 05-08]
    ws = _mon_fri_set(date(2026, 5, 1), date(2026, 5, 31))
    assert _workdays_between(date(2026, 5, 3), date(2026, 5, 8), ws) == 5


def test_workdays_between_start_equals_end_returns_zero():
    ws = _mon_fri_set(date(2026, 5, 1), date(2026, 5, 31))
    assert _workdays_between(date(2026, 5, 4), date(2026, 5, 4), ws) == 0


def test_workdays_between_falls_back_for_uncovered_dates():
    # Empty workday_set → fallback to Mon–Fri
    ws: frozenset[date] = frozenset()
    # Mon–Fri 2026-05-04 to 2026-05-08 = 5 workdays
    assert _workdays_between(date(2026, 5, 3), date(2026, 5, 8), ws) == 5


# ---------------------------------------------------------------------------
# _avg_workday_cycle
# ---------------------------------------------------------------------------

def test_avg_workday_cycle_two_dates_10_workdays_apart():
    # 2026-05-04 (Mon) to 2026-05-18 (Mon) = exactly 10 workdays
    ws = _mon_fri_set(date(2026, 5, 1), date(2026, 6, 30))
    dates = [date(2026, 5, 4), date(2026, 5, 18)]
    assert _avg_workday_cycle(dates, ws, max_days=120) == 10


def test_avg_workday_cycle_returns_none_for_single_date():
    ws = _mon_fri_set(date(2026, 5, 1), date(2026, 5, 31))
    assert _avg_workday_cycle([date(2026, 5, 4)], ws, max_days=120) is None


def test_avg_workday_cycle_excludes_gaps_over_max():
    ws = _mon_fri_set(date(2026, 1, 1), date(2026, 12, 31))
    # Two gaps: 5 workdays and 150 workdays (should be excluded by max_days=120)
    dates = [date(2026, 1, 5), date(2026, 1, 12), date(2026, 8, 1)]
    result = _avg_workday_cycle(dates, ws, max_days=120)
    # Only first gap (5 workdays) counts
    assert result == 5


def test_avg_workday_cycle_returns_none_when_all_gaps_over_max():
    ws = _mon_fri_set(date(2026, 1, 1), date(2026, 12, 31))
    dates = [date(2026, 1, 5), date(2026, 8, 1)]  # ~150 workday gap
    assert _avg_workday_cycle(dates, ws, max_days=120) is None


# ---------------------------------------------------------------------------
# _typical_shipment_qty
# ---------------------------------------------------------------------------

def test_typical_shipment_qty_median():
    assert _typical_shipment_qty([10, 20, 30, 40, 50]) == 30.0


def test_typical_shipment_qty_filters_zero():
    assert _typical_shipment_qty([0, 10, 20]) == 15.0


def test_typical_shipment_qty_empty_returns_zero():
    assert _typical_shipment_qty([]) == 0.0


# ---------------------------------------------------------------------------
# _project — core projection logic
# ---------------------------------------------------------------------------

def _ws() -> frozenset[date]:
    return _mon_fri_set(date(2026, 1, 1), date(2026, 12, 31))


def test_project_zero_remaining_when_next_shipment_after_month_end():
    ws = _ws()
    # cycle=20 workdays, last shipment today → next in 20 workdays, only 10 remaining
    today = date(2026, 5, 15)
    result = _project(
        order_dates=[date(2026, 4, 10), date(2026, 4, 30), date(2026, 5, 15)],
        order_quantities=[100, 100, 100],
        workday_set=ws,
        current_qty=50,
        latest_sales_date=today,
        today=today,
        workdays_remaining=10,
        has_daily_actual=True,
        max_cycle_days=120,
    )
    assert result.remaining_shipments == 0
    assert result.estimated_eom_qty == 50.0


def test_project_one_remaining_shipment():
    ws = _ws()
    today = date(2026, 5, 10)
    # cycle ≈ 10 workdays, last shipment was today (0 days ago), 15 remaining
    # workdays_until_next = 10, fits 1 shipment
    result = _project(
        order_dates=[date(2026, 4, 1), date(2026, 4, 15), date(2026, 5, 1)],
        order_quantities=[50, 50, 50],
        workday_set=ws,
        current_qty=30,
        latest_sales_date=today,
        today=today,
        workdays_remaining=15,
        has_daily_actual=True,
        max_cycle_days=120,
    )
    assert result.remaining_shipments == 1
    assert result.estimated_eom_qty == 30 + result.typical_qty_per_shipment


def test_project_low_confidence_for_sparse_history():
    ws = _ws()
    today = date(2026, 5, 10)
    result = _project(
        order_dates=[date(2026, 4, 1), date(2026, 4, 20)],  # only 2 dates
        order_quantities=[100, 100],
        workday_set=ws,
        current_qty=50,
        latest_sales_date=date(2026, 5, 5),
        today=today,
        workdays_remaining=15,
        has_daily_actual=True,
        max_cycle_days=120,
    )
    assert result.confidence == "low"


def test_project_high_confidence_with_enough_history_and_actuals():
    ws = _ws()
    today = date(2026, 5, 10)
    dates = [date(2026, 1, 5) + timedelta(weeks=4 * i) for i in range(6)]
    result = _project(
        order_dates=dates,
        order_quantities=[100] * 6,
        workday_set=ws,
        current_qty=50,
        latest_sales_date=date(2026, 5, 5),
        today=today,
        workdays_remaining=15,
        has_daily_actual=True,
        max_cycle_days=120,
    )
    assert result.confidence == "high"


def test_project_falls_back_to_current_qty_when_no_history():
    ws = _ws()
    result = _project(
        order_dates=[],
        order_quantities=[],
        workday_set=ws,
        current_qty=77,
        latest_sales_date=None,
        today=date(2026, 5, 10),
        workdays_remaining=15,
        has_daily_actual=False,
        max_cycle_days=120,
    )
    assert result.estimated_eom_qty == 77
    assert result.remaining_shipments == 0
    assert result.confidence == "low"


# ---------------------------------------------------------------------------
# batch_project_eom — integration with DB
# ---------------------------------------------------------------------------

def _insert_sales(db: MORDatabase, rows: list[dict]) -> None:
    with db.get_connection() as conn:
        for r in rows:
            conn.execute(
                "INSERT INTO sales_records (order_date, customer_name, product_code, quantity, unit_price, amount)"
                " VALUES (?, ?, ?, ?, 0, 0)",
                (r["date"], r["customer"], r["product"], r["qty"]),
            )
        conn.commit()


def _forecast_row(customer: str, product: str, cycle: int = 20) -> "ForecastRow":
    from src.backend.forecast_models import ForecastRow
    return ForecastRow(
        row_id=f"{customer}__{product}",
        customer=customer,
        product_code=product,
        product_name="Test",
        latest_order_date=date(2026, 4, 20),
        cycle_days=cycle,
        next_order_date=None,
        auto_in_month=False,
        last_year_same_month_qty=100,
        this_year_same_month_qty=30,
        latest_price=100,
        system_forecast=80,
        manual_adjustment=None,
        final_forecast=80,
        estimated_amount=8000,
        forecast_basis="data_driven",
    )


def test_batch_project_eom_uses_sales_records(tmp_path: Path):
    db = _db(tmp_path)
    # 6 monthly shipments for Hospital A / P1, each 100 units, ~20 workdays apart
    history_dates = [date(2025, 11, 3) + timedelta(days=28 * i) for i in range(6)]
    _insert_sales(db, [
        {"date": d.isoformat(), "customer": "Hospital A", "product": "P1", "qty": 100}
        for d in history_dates
    ])

    rows = [_forecast_row("Hospital A", "P1")]
    today = date(2026, 5, 10)
    results = batch_project_eom(db, rows, {}, today, 2026, 5)

    assert "Hospital A__P1" in results
    r = results["Hospital A__P1"]
    assert isinstance(r, ProjectionResult)
    assert r.typical_qty_per_shipment == 100.0
    assert r.workday_cycle is not None
    assert r.workday_cycle > 0


def test_batch_project_eom_excludes_current_month_from_history(tmp_path: Path):
    db = _db(tmp_path)
    # Insert one May-2026 row (should be excluded) and 5 historical rows
    history_dates = [date(2026, 1, 5) + timedelta(days=28 * i) for i in range(5)]
    _insert_sales(db, [
        {"date": d.isoformat(), "customer": "H", "product": "P1", "qty": 50}
        for d in history_dates
    ] + [{"date": "2026-05-04", "customer": "H", "product": "P1", "qty": 999}])

    rows = [_forecast_row("H", "P1")]
    results = batch_project_eom(db, rows, {}, date(2026, 5, 10), 2026, 5)

    r = results["H__P1"]
    # typical qty should be 50 (from history), not 999 (current month excluded)
    assert r.typical_qty_per_shipment == 50.0


def test_batch_project_eom_returns_low_confidence_for_empty_history(tmp_path: Path):
    db = _db(tmp_path)
    rows = [_forecast_row("X", "P1")]
    results = batch_project_eom(db, rows, {}, date(2026, 5, 10), 2026, 5)
    assert results["X__P1"].confidence == "low"
    assert results["X__P1"].estimated_eom_qty == 30.0  # falls back to this_year_same_month_qty


def _insert_daily_actuals(db: MORDatabase, rows: list[dict]) -> None:
    with db.get_connection() as conn:
        for r in rows:
            d = date.fromisoformat(r["date"])
            conn.execute(
                """INSERT INTO daily_sales_actuals
                   (sales_year, sales_month, sales_date, customer_name, product_code,
                    actual_quantity, taxed_amount)
                   VALUES (?, ?, ?, ?, ?, ?, 0)""",
                (d.year, d.month, r["date"], r["customer"], r["product"], r["qty"]),
            )
        conn.commit()


# ---------------------------------------------------------------------------
# batch_project_eom — current-month daily actuals integration
# ---------------------------------------------------------------------------

def test_batch_project_eom_includes_current_month_dates_in_gap_history(tmp_path: Path):
    """Current-month shipment dates from daily_sales_actuals must appear in gap_history."""
    db = _db(tmp_path)
    # 5 historical shipments (Apr 2026 and earlier), each ~20 workdays apart
    history_dates = [
        date(2026, 1, 5), date(2026, 1, 26), date(2026, 2, 16),
        date(2026, 3, 9), date(2026, 3, 30),
    ]
    _insert_sales(db, [
        {"date": d.isoformat(), "customer": "H", "product": "P1", "qty": 100}
        for d in history_dates
    ])
    # One shipment this month (2026-05-07) — only in daily_sales_actuals
    _insert_daily_actuals(db, [
        {"date": "2026-05-07", "customer": "H", "product": "P1", "qty": 100},
    ])

    from src.backend.daily_sales_importer import DailyActualAggregate
    actuals = {"H__P1": DailyActualAggregate(
        actual_quantity=100, taxed_amount=0, latest_sales_date="2026-05-07"
    )}
    rows = [_forecast_row("H", "P1")]
    results = batch_project_eom(db, rows, actuals, date(2026, 5, 13), 2026, 5)

    r = results["H__P1"]
    # gap_history is capped to last 8; the gap from 2026-03-30 → 2026-05-07 must be present
    assert len(r.gap_history) > 0
    # The last gap in history should reflect the current-month shipment date (May 7)
    # which is ~27 workdays after Mar 30 — certainly larger than a single week
    assert r.gap_history[-1] > 5


def test_batch_project_eom_current_month_actuals_only_reads_target_month(tmp_path: Path):
    """Only the target month's daily_sales_actuals rows must be merged; other months ignored."""
    db = _db(tmp_path)
    # 4 historical shipments so we have a cycle to work with
    history_dates = [
        date(2026, 1, 5), date(2026, 1, 26), date(2026, 2, 16), date(2026, 3, 9),
    ]
    _insert_sales(db, [
        {"date": d.isoformat(), "customer": "H", "product": "P1", "qty": 50}
        for d in history_dates
    ])
    # May data (target month) — should be included
    _insert_daily_actuals(db, [
        {"date": "2026-05-05", "customer": "H", "product": "P1", "qty": 50},
    ])
    # April data in daily_sales_actuals (closed month, shouldn't affect May projection)
    _insert_daily_actuals(db, [
        {"date": "2026-04-10", "customer": "H", "product": "P1", "qty": 999},
    ])

    rows = [_forecast_row("H", "P1")]
    results = batch_project_eom(db, rows, {}, date(2026, 5, 13), 2026, 5)

    r = results["H__P1"]
    # typical_qty median: 5 × 50 (history) + 1 × 50 (May actual) = all 50s → median 50
    # If April's 999 were included, median would be skewed
    assert r.typical_qty_per_shipment == 50.0


def test_batch_project_eom_cycle_reflects_current_month_when_long_gap(tmp_path: Path):
    """When current month has a shipment after an unusually long gap,
    the workday_cycle must be pulled toward the real recent interval."""
    db = _db(tmp_path)
    # 4 tight shipments ≈ 5 workdays apart (Jan–Feb)
    tight_dates = [
        date(2026, 1, 5), date(2026, 1, 12), date(2026, 1, 19), date(2026, 1, 26),
    ]
    _insert_sales(db, [
        {"date": d.isoformat(), "customer": "H", "product": "P1", "qty": 100}
        for d in tight_dates
    ])
    # Then a long gap: last historical = Jan 26, current-month = May 7 (~65 workdays)
    _insert_daily_actuals(db, [
        {"date": "2026-05-07", "customer": "H", "product": "P1", "qty": 100},
    ])

    from src.backend.daily_sales_importer import DailyActualAggregate
    actuals = {"H__P1": DailyActualAggregate(
        actual_quantity=100, taxed_amount=0, latest_sales_date="2026-05-07"
    )}
    rows = [_forecast_row("H", "P1")]
    results_with = batch_project_eom(db, rows, actuals, date(2026, 5, 13), 2026, 5)

    # Without current month actuals the cycle is ~5; with it the long gap is added
    assert results_with["H__P1"].workday_cycle is not None
    # cycle should be greater than the tight 5-workday average because the long gap is included
    assert results_with["H__P1"].workday_cycle > 5
