from pathlib import Path

import pandas as pd
import pytest

from src.backend.database import MORDatabase
from src.backend.history_service import (
    LastMonthPerformance,
    _past_n_months,
    _prev_month,
    fetch_last_month_actuals,
    fetch_last_month_budgets,
    fetch_last_month_performance,
    fetch_trend_6m,
)


@pytest.fixture
def db(tmp_path: Path) -> MORDatabase:
    return MORDatabase(tmp_path / "test.db")


def _insert_sales(db: MORDatabase, rows: list[dict]) -> None:
    with db.get_connection() as conn:
        for r in rows:
            conn.execute(
                "INSERT INTO sales_records (order_date, customer_name, product_code, quantity) VALUES (?, ?, ?, ?)",
                (r["order_date"], r["customer_name"], r["product_code"], r["quantity"]),
            )


def _insert_budgets(db: MORDatabase, rows: list[dict]) -> None:
    with db.get_connection() as conn:
        for r in rows:
            conn.execute(
                "INSERT INTO budget_targets (year, month, customer_name, product_code, target_quantity) VALUES (?, ?, ?, ?, ?)",
                (r["year"], r["month"], r["customer_name"], r["product_code"], r["target_quantity"]),
            )


# ── Pure helper tests (no DB needed) ─────────────────────────────────────────

def test_prev_month_normal():
    assert _prev_month(2026, 5) == (2026, 4)


def test_prev_month_january_wraps():
    assert _prev_month(2026, 1) == (2025, 12)


def test_past_n_months_returns_oldest_first():
    result = _past_n_months(2026, 4, 3)
    assert result == [(2026, 1), (2026, 2), (2026, 3)]


def test_past_n_months_wraps_year():
    result = _past_n_months(2026, 2, 3)
    assert result == [(2025, 11), (2025, 12), (2026, 1)]


# ── DB-backed tests ───────────────────────────────────────────────────────────

def test_fetch_last_month_actuals(db: MORDatabase):
    _insert_sales(db, [
        {"order_date": "2026-04-10", "customer_name": "A", "product_code": "P1", "quantity": 5.0},
        {"order_date": "2026-04-20", "customer_name": "A", "product_code": "P1", "quantity": 3.0},
    ])
    result = fetch_last_month_actuals(db, target_year=2026, target_month=5)
    assert result["A__P1"] == 8.0


def test_fetch_last_month_actuals_empty_when_no_data(db: MORDatabase):
    result = fetch_last_month_actuals(db, target_year=2026, target_month=5)
    assert result == {}


def test_fetch_last_month_performance_merges_actuals_and_budgets(db: MORDatabase):
    _insert_sales(db, [
        {"order_date": "2026-04-15", "customer_name": "A", "product_code": "P1", "quantity": 10.0},
    ])
    _insert_budgets(db, [
        {"year": 2026, "month": 4, "customer_name": "A", "product_code": "P1", "target_quantity": 20.0},
    ])
    result = fetch_last_month_performance(db, target_year=2026, target_month=5)
    perf = result["A__P1"]
    assert isinstance(perf, LastMonthPerformance)
    assert perf.actual == 10.0
    assert perf.budget == 20.0
    assert perf.gap == -10.0
    assert perf.achievement_rate == 50.0


def test_fetch_trend_6m_returns_length_6(db: MORDatabase):
    _insert_sales(db, [
        {"order_date": "2026-03-10", "customer_name": "A", "product_code": "P1", "quantity": 7.0},
    ])
    result = fetch_trend_6m(db, target_year=2026, target_month=5)
    assert len(result["A__P1"]) == 6
    # 6 months before May: Nov, Dec, Jan, Feb, Mar, Apr → March is index 4
    assert result["A__P1"][4] == 7.0
