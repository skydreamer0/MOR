from pathlib import Path

import pytest

from src.backend.database import MORDatabase
from src.backend.monthly_review_data import MonthlyReviewDataReader
from src.backend.row_identity import make_row_id


def _db(tmp_path: Path) -> MORDatabase:
    return MORDatabase(tmp_path / "mor_workbench.db")


def _insert_daily_actual(
    db: MORDatabase,
    year: int,
    month: int,
    customer: str,
    product: str,
    qty: float,
    amount: float,
    *,
    product_name: str = "",
    sales_date: str | None = None,
) -> None:
    with db.get_connection() as conn:
        conn.execute(
            """
            INSERT INTO daily_import_batches
            (source_filename, source_hash, sales_year, sales_month,
             row_count, quantity_total, taxed_amount_total, status)
            VALUES ('test.xlsx', 'hash', ?, ?, 1, ?, ?, 'success')
            """,
            (year, month, qty, amount),
        )
        batch_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            """
            INSERT INTO daily_sales_actuals
            (sales_year, sales_month, sales_date, customer_name, product_code,
             product_name, actual_quantity, taxed_amount, import_batch_id,
             customer_code, sales_quantity, gift_quantity, net_unit_price, bonus_basis_amount)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '', ?, 0, 0, 0)
            """,
            (
                year,
                month,
                sales_date or f"{year}-{month:02d}-10",
                customer,
                product,
                product_name,
                qty,
                amount,
                batch_id,
                qty,
            ),
        )


def _close_month(db: MORDatabase, year: int, month: int, snapshot_id: int | None = None) -> None:
    with db.get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO month_close_records
            (year, month, actual_row_count, actual_quantity_total,
             actual_amount_total, final_snapshot_id)
            VALUES (?, ?, 1, 1, 1, ?)
            """,
            (year, month, snapshot_id),
        )


def _insert_sales_record(
    db: MORDatabase,
    order_date: str,
    customer: str,
    product: str,
    qty: float,
    amount: float,
    *,
    product_name: str = "",
) -> None:
    with db.get_connection() as conn:
        conn.execute(
            """
            INSERT INTO sales_records
            (order_date, customer_name, product_code, product_name, quantity, unit_price, amount)
            VALUES (?, ?, ?, ?, ?, 0, ?)
            """,
            (order_date, customer, product, product_name, qty, amount),
        )


def _insert_budget(
    db: MORDatabase,
    year: int,
    month: int,
    customer: str,
    product: str,
    qty: float,
    amount: float,
    base_qty: float = 0.0,
) -> None:
    with db.get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO budget_targets
            (year, month, customer_name, product_code, target_quantity, target_amount, base_target_quantity)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (year, month, customer, product, qty, amount, base_qty),
        )


def _set_price_quantity(db: MORDatabase, product: str, price_quantity: float) -> None:
    with db.get_connection() as conn:
        conn.execute(
            """
            INSERT INTO item_configs (product_code, price_quantity)
            VALUES (?, ?)
            ON CONFLICT(product_code) DO UPDATE SET price_quantity = excluded.price_quantity
            """,
            (product, price_quantity),
        )


def _insert_snapshot(db: MORDatabase, year: int, month: int, rows: list[dict]) -> int:
    with db.get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO forecast_snapshots (snapshot_name, snapshot_type, year, month, created_by)
            VALUES ('close', 'CloseMonth', ?, ?, 'test')
            """,
            (year, month),
        )
        snapshot_id = int(cursor.lastrowid)
        for row in rows:
            conn.execute(
                """
                INSERT INTO snapshot_items
                (snapshot_id, customer_name, product_code, system_forecast, final_forecast)
                VALUES (?, ?, ?, ?, ?)
                """,
                (snapshot_id, row["customer"], row["product"], row["forecast"], row["forecast"]),
            )
    return snapshot_id


def test_customer_amounts_use_closed_daily_actuals_and_open_sales_records(tmp_path: Path):
    db = _db(tmp_path)
    _insert_daily_actual(db, 2026, 5, "A", "P1", 1, 100)
    _insert_sales_record(db, "2026-05-11", "A", "P1", 1, 999)
    _close_month(db, 2026, 5)
    _insert_sales_record(db, "2026-06-11", "B", "P2", 1, 250)

    reader = MonthlyReviewDataReader(db)

    assert reader.customer_amounts(2026, 5) == {"A": 100.0}
    assert reader.customer_amounts(2026, 6) == {"B": 250.0}


def test_product_totals_use_closed_daily_actuals_and_open_sales_records(tmp_path: Path):
    db = _db(tmp_path)
    _insert_daily_actual(db, 2026, 5, "A", "P1", 2, 100, product_name="Daily P1")
    _insert_sales_record(db, "2026-05-12", "A", "P1", 5, 999, product_name="Sales P1")
    _close_month(db, 2026, 5)
    _insert_sales_record(db, "2026-06-12", "B", "P2", 3, 300, product_name="Sales P2")

    reader = MonthlyReviewDataReader(db)

    closed_amounts, closed_qtys, closed_names = reader.product_totals(2026, 5)
    open_amounts, open_qtys, open_names = reader.product_totals(2026, 6)

    assert closed_amounts == {"P1": 100.0}
    assert closed_qtys == {"P1": 2.0}
    assert closed_names == {"P1": "Daily P1"}
    assert open_amounts == {"P2": 300.0}
    assert open_qtys == {"P2": 3.0}
    assert open_names == {"P2": "Sales P2"}


def test_product_names_prefer_daily_then_sales_then_current_month(tmp_path: Path):
    db = _db(tmp_path)
    _insert_daily_actual(db, 2026, 5, "A", "P1", 1, 100, product_name="Daily Name")
    _insert_sales_record(db, "2026-04-01", "A", "P2", 1, 200, product_name="Sales Name")
    with db.get_connection() as conn:
        conn.execute(
            """
            INSERT INTO current_month_records
            (order_date, customer_name, product_code, product_name, quantity, unit_price, amount)
            VALUES ('2026-06-01', 'A', 'P3', 'Current Name', 1, 0, 300)
            """
        )

    names = MonthlyReviewDataReader(db).product_names()

    assert names["P1"] == "Daily Name"
    assert names["P2"] == "Sales Name"
    assert names["P3"] == "Current Name"


def test_budget_rows_and_snapshot_forecasts_are_keyed_by_row_identity(tmp_path: Path):
    db = _db(tmp_path)
    _insert_budget(db, 2026, 5, "A", "P1", 10, 1000, 2)
    snapshot_id = _insert_snapshot(db, 2026, 5, [{"customer": "A", "product": "P1", "forecast": 8}])
    _close_month(db, 2026, 5, snapshot_id)

    reader = MonthlyReviewDataReader(db)
    row_id = make_row_id("A", "P1")

    assert reader.budget_rows(2026, 5)[row_id] == {
        "target_quantity": 10.0,
        "target_amount": 1000.0,
        "base_target_quantity": 2.0,
    }
    assert reader.snapshot_forecasts(2026, 5)[row_id] == {"final_forecast": 8.0}


def test_quantity_multiplier_uses_positive_price_quantity(tmp_path: Path):
    db = _db(tmp_path)
    _set_price_quantity(db, "P1", 280)

    reader = MonthlyReviewDataReader(db)

    assert reader.price_quantities() == {"P1": 280.0}
    assert reader.quantity_multiplier("P1") == 280.0
    assert reader.quantity_multiplier("UNKNOWN") == 1.0


def test_forecast_amounts_use_period_price_and_price_quantity(tmp_path: Path):
    db = _db(tmp_path)
    _set_price_quantity(db, "P1", 10)
    _insert_daily_actual(db, 2026, 5, "A", "P1", 2, 100)
    snapshot_id = _insert_snapshot(db, 2026, 5, [{"customer": "A", "product": "P1", "forecast": 50}])
    _close_month(db, 2026, 5, snapshot_id)

    amounts = MonthlyReviewDataReader(db).forecast_amounts(2026, 5)

    assert amounts[("A", "P1")] == pytest.approx(250.0)


def test_forecast_amounts_historical_fallback_is_explicit(tmp_path: Path):
    db = _db(tmp_path)
    _insert_sales_record(db, "2026-04-01", "B", "P2", 2, 40)
    snapshot_id = _insert_snapshot(db, 2026, 5, [{"customer": "B", "product": "P2", "forecast": 4}])
    _close_month(db, 2026, 5, snapshot_id)

    reader = MonthlyReviewDataReader(db)

    assert reader.forecast_amounts(2026, 5) == {}
    assert reader.forecast_amounts(2026, 5, historical_fallback=True)[("B", "P2")] == pytest.approx(80.0)

