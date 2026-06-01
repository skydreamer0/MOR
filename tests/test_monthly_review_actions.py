"""Tests for monthly_review_actions (lost / priority / declining / new)."""
from pathlib import Path

from src.backend.database import MORDatabase
from src.backend.monthly_review_actions import (
    YOY_DROP_THRESHOLD,
    build_action_lists,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _db(tmp_path: Path) -> MORDatabase:
    return MORDatabase(tmp_path / "mor_workbench.db")


def _insert_actuals(
    db: MORDatabase, year: int, month: int, rows: list[dict],
) -> None:
    """rows: [{customer, product, qty, pretax}, ...]"""
    with db.get_connection() as conn:
        conn.execute(
            """INSERT INTO daily_import_batches
            (source_filename, source_hash, sales_year, sales_month,
             row_count, quantity_total, taxed_amount_total, status)
            VALUES ('t.xlsx', ?, ?, ?, ?, ?, 0, 'success')""",
            (f"{year}-{month}", year, month, len(rows), sum(r["qty"] for r in rows)),
        )
        batch_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        for r in rows:
            # `pretax` key kept for back-compat in test data — written into
            # taxed_amount (含稅淨額) which is now the primary review column.
            conn.execute(
                """INSERT INTO daily_sales_actuals
                (sales_year, sales_month, sales_date, customer_name, product_code,
                 actual_quantity, taxed_amount, bonus_basis_amount,
                 net_unit_price, import_batch_id, customer_code, product_name,
                 sales_quantity, gift_quantity)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, ?, '', '', ?, 0)""",
                (year, month, f"{year}-{month:02d}-10",
                 r["customer"], r["product"], r["qty"], r["pretax"],
                 batch_id, r["qty"]),
            )
        # Mark month closed so the loader uses daily_sales_actuals
        conn.execute(
            """INSERT OR IGNORE INTO month_close_records (year, month, actual_row_count,
            actual_quantity_total, actual_amount_total)
            VALUES (?, ?, 1, 1, 1)""",
            (year, month),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_lost_list_includes_customers_with_last_year_but_no_current(tmp_path: Path):
    db = _db(tmp_path)
    _insert_actuals(db, 2026, 5, [{"customer": "Active", "product": "P", "qty": 10, "pretax": 1000}])
    _insert_actuals(db, 2025, 5, [
        {"customer": "Active",  "product": "P", "qty": 10, "pretax": 900},
        {"customer": "LostBig", "product": "P", "qty": 50, "pretax": 5000},
        {"customer": "LostSm",  "product": "P", "qty": 5,  "pretax": 500},
    ])

    lists = build_action_lists(db, 2026, 5)

    lost_names = [c.customer_name for c in lists.lost]
    assert "LostBig" in lost_names
    assert "LostSm"  in lost_names
    assert "Active"  not in lost_names
    # sorted by last_year_amount desc
    assert lists.lost[0].customer_name == "LostBig"


def test_new_list_includes_customers_present_this_year_only(tmp_path: Path):
    db = _db(tmp_path)
    _insert_actuals(db, 2026, 5, [
        {"customer": "Existing", "product": "P", "qty": 10, "pretax": 1000},
        {"customer": "Newbie",   "product": "P", "qty": 5,  "pretax": 500},
    ])
    _insert_actuals(db, 2025, 5, [{"customer": "Existing", "product": "P", "qty": 8, "pretax": 800}])

    lists = build_action_lists(db, 2026, 5)

    assert [c.customer_name for c in lists.new] == ["Newbie"]


def test_priority_list_requires_yoy_drop_and_top_amount(tmp_path: Path):
    db = _db(tmp_path)
    # 10 customers so the top-20% cutoff selects the top 2.
    # BigDrop is #2 by current amount AND dropped 40% → qualifies.
    # BigFlat is #1 by current amount but barely dropped → filtered out (drop too small).
    # TinyDrop dropped 50% but is way below the cutoff → filtered out.
    current = [
        {"customer": "BigFlat", "product": "P", "qty": 100, "pretax": 10000},
        {"customer": "BigDrop", "product": "P", "qty": 80,  "pretax": 8000},
    ] + [
        {"customer": f"Mid{i}", "product": "P", "qty": 5, "pretax": 500} for i in range(7)
    ] + [
        {"customer": "TinyDrop", "product": "P", "qty": 1, "pretax": 100},
    ]
    last_year = [
        {"customer": "BigFlat", "product": "P", "qty": 100, "pretax": 10500},
        {"customer": "BigDrop", "product": "P", "qty": 130, "pretax": 13000},
    ] + [
        {"customer": f"Mid{i}", "product": "P", "qty": 5, "pretax": 500} for i in range(7)
    ] + [
        {"customer": "TinyDrop", "product": "P", "qty": 2, "pretax": 200},
    ]
    _insert_actuals(db, 2026, 5, current)
    _insert_actuals(db, 2025, 5, last_year)

    lists = build_action_lists(db, 2026, 5)

    names = [c.customer_name for c in lists.priority]
    assert "BigDrop"  in names
    assert "BigFlat"  not in names
    assert "TinyDrop" not in names
    p = next(c for c in lists.priority if c.customer_name == "BigDrop")
    assert p.yoy_drop >= YOY_DROP_THRESHOLD


def test_declining_list_requires_strict_three_month_decline(tmp_path: Path):
    db = _db(tmp_path)
    # Declining: 5000 → 3000 → 1000
    _insert_actuals(db, 2026, 3, [{"customer": "Slipping", "product": "P", "qty": 50, "pretax": 5000}])
    _insert_actuals(db, 2026, 4, [{"customer": "Slipping", "product": "P", "qty": 30, "pretax": 3000}])
    _insert_actuals(db, 2026, 5, [{"customer": "Slipping", "product": "P", "qty": 10, "pretax": 1000}])
    # Not strictly declining (went up in month 4)
    _insert_actuals(db, 2026, 3, [{"customer": "Bouncy", "product": "P", "qty": 30, "pretax": 3000}])
    _insert_actuals(db, 2026, 4, [{"customer": "Bouncy", "product": "P", "qty": 50, "pretax": 5000}])
    _insert_actuals(db, 2026, 5, [{"customer": "Bouncy", "product": "P", "qty": 20, "pretax": 2000}])

    lists = build_action_lists(db, 2026, 5)

    names = [c.customer_name for c in lists.declining]
    assert "Slipping" in names
    assert "Bouncy"   not in names
