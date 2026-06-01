"""Tests for monthly_review_products."""
from pathlib import Path

from src.backend.database import MORDatabase
from src.backend.monthly_review_products import build_product_summary


def _db(tmp_path: Path) -> MORDatabase:
    return MORDatabase(tmp_path / "mor_workbench.db")


def _insert(db, year, month, rows):
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


def test_products_ranked_by_amount_with_share(tmp_path):
    db = _db(tmp_path)
    _insert(db, 2026, 5, [
        {"customer": "A", "product": "P1", "qty": 10, "amount": 8000, "name": "蘋果"},
        {"customer": "B", "product": "P1", "qty": 5,  "amount": 2000, "name": "蘋果"},
        {"customer": "A", "product": "P2", "qty": 3,  "amount": 5000, "name": "葡萄"},
    ])
    ps = build_product_summary(db, 2026, 5)
    by_code = {r.product_code: r for r in ps.rows}

    # P1 = 10000, P2 = 5000, total = 15000
    assert by_code["P1"].rank == 1
    assert by_code["P1"].actual_amount == 10000
    assert abs(by_code["P1"].revenue_share - 10000 / 15000) < 1e-6
    assert by_code["P2"].rank == 2


def test_product_yoy_and_rank_change(tmp_path):
    db = _db(tmp_path)
    _insert(db, 2025, 5, [
        {"customer": "A", "product": "P1", "qty": 5, "amount": 5000},
        {"customer": "A", "product": "P2", "qty": 3, "amount": 3000},
    ])
    _insert(db, 2026, 5, [
        {"customer": "A", "product": "P1", "qty": 8, "amount": 8000},
        {"customer": "A", "product": "P2", "qty": 2, "amount": 1500},
    ])
    ps = build_product_summary(db, 2026, 5)
    by_code = {r.product_code: r for r in ps.rows}
    assert abs(by_code["P1"].yoy_growth - 1.6) < 1e-6
    assert abs(by_code["P2"].yoy_growth - 0.5) < 1e-6
    # ranks unchanged
    assert by_code["P1"].last_year_rank == 1 and by_code["P1"].rank == 1
    assert by_code["P2"].last_year_rank == 2 and by_code["P2"].rank == 2
