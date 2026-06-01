"""Tests for monthly_review_trend."""
from pathlib import Path

from src.backend.database import MORDatabase
from src.backend.monthly_review_trend import build_trend


def _db(tmp_path: Path) -> MORDatabase:
    return MORDatabase(tmp_path / "mor_workbench.db")


def _insert_actual(db, year, month, amount):
    with db.get_connection() as conn:
        conn.execute(
            """INSERT INTO daily_import_batches
            (source_filename, source_hash, sales_year, sales_month,
             row_count, quantity_total, taxed_amount_total, status)
            VALUES ('t.xlsx', ?, ?, ?, 1, 1, ?, 'success')""",
            (f"{year}-{month}", year, month, amount),
        )
        bid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            """INSERT INTO daily_sales_actuals
            (sales_year, sales_month, sales_date, customer_name, product_code,
             actual_quantity, taxed_amount, bonus_basis_amount, net_unit_price,
             import_batch_id, customer_code, product_name, sales_quantity, gift_quantity)
            VALUES (?, ?, ?, 'A', 'P1', 10, ?, 0, 0, ?, '', '', 10, 0)""",
            (year, month, f"{year}-{month:02d}-10", amount, bid),
        )
        conn.execute(
            """INSERT OR IGNORE INTO month_close_records (year, month, actual_row_count,
            actual_quantity_total, actual_amount_total) VALUES (?, ?, 1, 10, ?)""",
            (year, month, amount),
        )
        conn.commit()


def test_trend_returns_n_points_oldest_first(tmp_path):
    db = _db(tmp_path)
    _insert_actual(db, 2026, 3, 1000)
    _insert_actual(db, 2026, 4, 2000)
    _insert_actual(db, 2026, 5, 3000)

    ts = build_trend(db, 2026, 5, months=3)

    assert [(p.year, p.month) for p in ts.points] == [(2026, 3), (2026, 4), (2026, 5)]
    assert [p.actual for p in ts.points] == [1000.0, 2000.0, 3000.0]
    assert ts.points[-1].label == "26/05"


def test_trend_wraps_year_boundary(tmp_path):
    db = _db(tmp_path)
    _insert_actual(db, 2025, 11, 100)
    _insert_actual(db, 2025, 12, 200)
    _insert_actual(db, 2026, 1,  300)

    ts = build_trend(db, 2026, 1, months=3)
    assert [(p.year, p.month) for p in ts.points] == [(2025, 11), (2025, 12), (2026, 1)]
