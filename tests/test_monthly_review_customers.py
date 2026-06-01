"""Tests for monthly_review_customers."""
from pathlib import Path

from src.backend.database import MORDatabase
from src.backend.monthly_review_customers import build_customer_summary


def _db(tmp_path: Path) -> MORDatabase:
    return MORDatabase(tmp_path / "mor_workbench.db")


def _insert(db, year, month, rows):
    """rows: [{customer, product, qty, amount}]"""
    with db.get_connection() as conn:
        conn.execute(
            """INSERT INTO daily_import_batches
            (source_filename, source_hash, sales_year, sales_month,
             row_count, quantity_total, taxed_amount_total, status)
            VALUES ('t.xlsx', ?, ?, ?, ?, ?, 0, 'success')""",
            (f"{year}-{month}", year, month, len(rows), sum(r["qty"] for r in rows)),
        )
        bid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        for r in rows:
            conn.execute(
                """INSERT INTO daily_sales_actuals
                (sales_year, sales_month, sales_date, customer_name, product_code,
                 actual_quantity, taxed_amount, bonus_basis_amount, net_unit_price,
                 import_batch_id, customer_code, product_name, sales_quantity, gift_quantity)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, ?, '', ?, ?, 0)""",
                (year, month, f"{year}-{month:02d}-10", r["customer"], r["product"],
                 r["qty"], r["amount"], bid, r.get("name", ""), r["qty"]),
            )
        conn.execute(
            """INSERT OR IGNORE INTO month_close_records (year, month, actual_row_count,
            actual_quantity_total, actual_amount_total) VALUES (?, ?, 1, 1, 1)""",
            (year, month),
        )
        conn.commit()


def test_ranks_by_current_amount_desc(tmp_path):
    db = _db(tmp_path)
    _insert(db, 2026, 5, [
        {"customer": "Small", "product": "P", "qty": 1, "amount": 100},
        {"customer": "Big",   "product": "P", "qty": 10, "amount": 5000},
        {"customer": "Mid",   "product": "P", "qty": 5, "amount": 1000},
    ])
    cs = build_customer_summary(db, 2026, 5)
    assert [r.customer_name for r in cs.rows] == ["Big", "Mid", "Small"]
    assert [r.rank for r in cs.rows] == [1, 2, 3]


def test_rank_change_vs_last_year(tmp_path):
    db = _db(tmp_path)
    # Last year: A=#1, B=#2, C absent
    _insert(db, 2025, 5, [
        {"customer": "A", "product": "P", "qty": 5, "amount": 5000},
        {"customer": "B", "product": "P", "qty": 3, "amount": 3000},
    ])
    # Current: C=#1 (new), B=#2, A=#3
    _insert(db, 2026, 5, [
        {"customer": "A", "product": "P", "qty": 1, "amount": 1000},
        {"customer": "B", "product": "P", "qty": 4, "amount": 4000},
        {"customer": "C", "product": "P", "qty": 6, "amount": 6000},
    ])
    cs = build_customer_summary(db, 2026, 5)
    by_name = {r.customer_name: r for r in cs.rows}
    assert by_name["C"].rank == 1 and by_name["C"].last_year_rank is None  # 新進
    assert by_name["B"].rank == 2 and by_name["B"].last_year_rank == 2     # 持平
    assert by_name["A"].rank == 3 and by_name["A"].last_year_rank == 1     # ↓2


def test_products_drill_down_per_customer(tmp_path):
    db = _db(tmp_path)
    _insert(db, 2026, 5, [
        {"customer": "A", "product": "P1", "qty": 5, "amount": 500, "name": "蘋果"},
        {"customer": "A", "product": "P2", "qty": 3, "amount": 2000, "name": "葡萄"},
        {"customer": "B", "product": "P1", "qty": 1, "amount": 100},
    ])
    cs = build_customer_summary(db, 2026, 5)
    a = next(r for r in cs.rows if r.customer_name == "A")
    # P2 first (higher amount)
    assert [p.product_code for p in a.products] == ["P2", "P1"]
    assert a.products[0].product_name == "葡萄"
