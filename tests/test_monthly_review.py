"""Tests for monthly_review service — DB-only, no Excel dependency."""
from datetime import date
from pathlib import Path

import pytest

from src.backend.database import MORDatabase
from src.backend.monthly_review import build_monthly_review, list_reviewable_months


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _db(tmp_path: Path) -> MORDatabase:
    return MORDatabase(tmp_path / "mor_workbench.db")


def _insert_actuals(db: MORDatabase, year: int, month: int, rows: list[dict]) -> None:
    with db.get_connection() as conn:
        conn.execute(
            """
            INSERT INTO daily_import_batches
            (source_filename, source_hash, sales_year, sales_month,
             row_count, quantity_total, taxed_amount_total, status)
            VALUES ('test.xlsx', 'abc', ?, ?, ?, ?, ?, 'success')
            """,
            (year, month, len(rows),
             sum(r["qty"] for r in rows),
             sum(r["amount"] for r in rows)),
        )
        batch_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        for r in rows:
            conn.execute(
                """
                INSERT INTO daily_sales_actuals
                (sales_year, sales_month, sales_date, customer_name, product_code,
                 actual_quantity, taxed_amount, import_batch_id,
                 customer_code, product_name, sales_quantity, gift_quantity,
                 net_unit_price, bonus_basis_amount)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, '', '', ?, 0, 0, 0)
                """,
                (year, month, f"{year}-{month:02d}-10",
                 r["customer"], r["product"], r["qty"], r["amount"],
                 batch_id, r["qty"]),
            )
        conn.commit()


def _insert_snapshot(db: MORDatabase, year: int, month: int, rows: list[dict]) -> int:
    with db.get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO forecast_snapshots (snapshot_name, snapshot_type, year, month, created_by)"
            " VALUES (?, 'CloseMonth', ?, ?, 'test')",
            (f"close {year}/{month}", year, month),
        )
        sid = cursor.lastrowid
        for r in rows:
            conn.execute(
                "INSERT INTO snapshot_items"
                " (snapshot_id, customer_name, product_code, system_forecast, final_forecast)"
                " VALUES (?, ?, ?, ?, ?)",
                (sid, r["customer"], r["product"], r["fcst"], r["fcst"]),
            )
        conn.commit()
    return sid


def _close_month(db: MORDatabase, year: int, month: int, snapshot_id: int) -> None:
    with db.get_connection() as conn:
        conn.execute(
            """
            INSERT INTO month_close_records
            (year, month, actual_row_count, actual_quantity_total,
             actual_amount_total, final_snapshot_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (year, month, 1, 100.0, 50000.0, snapshot_id),
        )
        conn.commit()


def _insert_budget(db: MORDatabase, year: int, month: int, customer: str, product: str, qty: float) -> None:
    with db.get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO budget_targets (year, month, customer_name, product_code, target_quantity, target_amount)"
            " VALUES (?, ?, ?, ?, ?, 0)",
            (year, month, customer, product, qty),
        )
        conn.commit()


def _insert_sales_record(db: MORDatabase, order_date: str, customer: str, product: str, qty: float) -> None:
    with db.get_connection() as conn:
        conn.execute(
            "INSERT INTO sales_records (order_date, customer_name, product_code, quantity, unit_price, amount)"
            " VALUES (?, ?, ?, ?, 0, 0)",
            (order_date, customer, product, qty),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_build_monthly_review_raises_if_not_closed(tmp_path: Path):
    db = _db(tmp_path)
    with pytest.raises(ValueError, match="尚未結月"):
        build_monthly_review(db, 2026, 5)


def test_build_monthly_review_totals(tmp_path: Path):
    db = _db(tmp_path)
    _insert_actuals(db, 2026, 5, [
        {"customer": "A", "product": "P1", "qty": 100, "amount": 10000},
        {"customer": "B", "product": "P2", "qty": 50, "amount": 5000},
    ])
    sid = _insert_snapshot(db, 2026, 5, [
        {"customer": "A", "product": "P1", "fcst": 90},
        {"customer": "B", "product": "P2", "fcst": 60},
    ])
    _close_month(db, 2026, 5, sid)

    summary = build_monthly_review(db, 2026, 5)

    assert summary.actual_quantity_total == 150
    assert summary.forecast_quantity_total == 150
    assert summary.actual_amount_total == 15000
    assert len(summary.rows) == 2


def test_forecast_accuracy_computed_correctly(tmp_path: Path):
    db = _db(tmp_path)
    _insert_actuals(db, 2026, 5, [{"customer": "A", "product": "P1", "qty": 80, "amount": 8000}])
    sid = _insert_snapshot(db, 2026, 5, [{"customer": "A", "product": "P1", "fcst": 100}])
    _close_month(db, 2026, 5, sid)

    summary = build_monthly_review(db, 2026, 5)
    row = summary.rows[0]

    assert row.forecast_gap == -20          # actual 80 - forecast 100
    assert row.forecast_accuracy == pytest.approx(0.8)
    assert summary.forecast_accuracy_total == pytest.approx(0.8)


def test_yoy_growth_uses_sales_records_when_last_year_not_closed(tmp_path: Path):
    db = _db(tmp_path)
    _insert_actuals(db, 2026, 5, [{"customer": "A", "product": "P1", "qty": 120, "amount": 12000}])
    sid = _insert_snapshot(db, 2026, 5, [{"customer": "A", "product": "P1", "fcst": 110}])
    _close_month(db, 2026, 5, sid)
    # Last year data in sales_records (not closed)
    _insert_sales_record(db, "2025-05-10", "A", "P1", 100)

    summary = build_monthly_review(db, 2026, 5)
    row = summary.rows[0]

    assert row.last_year_quantity == 100
    assert row.yoy_growth == pytest.approx(1.2)


def test_budget_achievement_computed_from_budget_targets(tmp_path: Path):
    db = _db(tmp_path)
    _insert_actuals(db, 2026, 5, [{"customer": "A", "product": "P1", "qty": 90, "amount": 9000}])
    sid = _insert_snapshot(db, 2026, 5, [{"customer": "A", "product": "P1", "fcst": 90}])
    _close_month(db, 2026, 5, sid)
    _insert_budget(db, 2026, 5, "A", "P1", 100)

    summary = build_monthly_review(db, 2026, 5)
    row = summary.rows[0]

    assert row.budget_quantity == 100
    assert row.budget_achievement == pytest.approx(0.9)
    assert summary.budget_achievement_total == pytest.approx(0.9)


def test_list_reviewable_months_only_includes_snapshot_linked_months(tmp_path: Path):
    db = _db(tmp_path)
    # Month with snapshot
    _insert_actuals(db, 2026, 4, [{"customer": "A", "product": "P1", "qty": 50, "amount": 5000}])
    sid = _insert_snapshot(db, 2026, 4, [{"customer": "A", "product": "P1", "fcst": 50}])
    _close_month(db, 2026, 4, sid)
    # Month without snapshot (manual close with no snapshot_id)
    _insert_actuals(db, 2026, 3, [{"customer": "A", "product": "P1", "qty": 40, "amount": 4000}])
    with db.get_connection() as conn:
        conn.execute(
            "INSERT INTO month_close_records (year, month, actual_row_count, actual_quantity_total, actual_amount_total)"
            " VALUES (2026, 3, 1, 40, 4000)",
        )
        conn.commit()

    months = list_reviewable_months(db)

    assert (2026, 4) in months
    assert (2026, 3) not in months  # no final_snapshot_id
