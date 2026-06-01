"""Tests for monthly_review_forecast_bias."""
from pathlib import Path

from src.backend.database import MORDatabase
from src.backend.monthly_review_forecast_bias import build_forecast_bias


def _db(tmp_path: Path) -> MORDatabase:
    return MORDatabase(tmp_path / "mor_workbench.db")


def _close_with_snapshot(db, year, month, actuals, forecasts):
    """actuals: [{customer, product, qty, amount}], forecasts: [{customer, product, fcst}]"""
    with db.get_connection() as conn:
        conn.execute(
            """INSERT INTO daily_import_batches
            (source_filename, source_hash, sales_year, sales_month,
             row_count, quantity_total, taxed_amount_total, status)
            VALUES ('t.xlsx', ?, ?, ?, ?, ?, 0, 'success')""",
            (f"{year}-{month}", year, month, len(actuals), sum(r["qty"] for r in actuals)),
        )
        bid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        for r in actuals:
            conn.execute(
                """INSERT INTO daily_sales_actuals
                (sales_year, sales_month, sales_date, customer_name, product_code,
                 actual_quantity, taxed_amount, bonus_basis_amount, net_unit_price,
                 import_batch_id, customer_code, product_name, sales_quantity, gift_quantity)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, ?, '', ?, ?, 0)""",
                (year, month, f"{year}-{month:02d}-10", r["customer"], r["product"],
                 r["qty"], r["amount"], bid, r.get("name", ""), r["qty"]),
            )
        cursor = conn.execute(
            """INSERT INTO forecast_snapshots
            (snapshot_name, snapshot_type, year, month, created_by)
            VALUES (?, 'CloseMonth', ?, ?, 'test')""",
            (f"close-{year}-{month}", year, month),
        )
        sid = cursor.lastrowid
        for f in forecasts:
            conn.execute(
                """INSERT INTO snapshot_items
                (snapshot_id, customer_name, product_code, system_forecast, final_forecast)
                VALUES (?, ?, ?, ?, ?)""",
                (sid, f["customer"], f["product"], f["fcst"], f["fcst"]),
            )
        conn.execute(
            """INSERT OR IGNORE INTO month_close_records
            (year, month, actual_row_count, actual_quantity_total, actual_amount_total,
             final_snapshot_id) VALUES (?, ?, 1, 1, 1, ?)""",
            (year, month, sid),
        )
        conn.commit()


def _set_price_quantity(db, product, price_quantity):
    with db.get_connection() as conn:
        conn.execute(
            "INSERT INTO item_configs (product_code, price_quantity) VALUES (?, ?) "
            "ON CONFLICT(product_code) DO UPDATE SET price_quantity = excluded.price_quantity",
            (product, price_quantity),
        )
        conn.commit()


def test_over_forecast_flagged_when_forecast_consistently_exceeds_actual(tmp_path):
    db = _db(tmp_path)
    # 3 months: forecast 100 qty * price 10 = 1000 forecast, actual 80 qty * price 10 = 800
    # avg ratio = 800/1000 = 0.8 → over-forecast by 20%
    for m in (3, 4, 5):
        _close_with_snapshot(
            db, 2026, m,
            actuals=[{"customer": "A", "product": "P1", "qty": 80, "amount": 800}],
            forecasts=[{"customer": "A", "product": "P1", "fcst": 100}],
        )
    bias = build_forecast_bias(db, 2026, 5, lookback=3)
    over = [r for r in bias.over_forecast if (r.customer_name, r.product_code) == ("A", "P1")]
    assert over and over[0].direction == "over"
    assert abs(over[0].avg_accuracy - 0.8) < 1e-6


def test_under_forecast_flagged_when_forecast_consistently_below_actual(tmp_path):
    db = _db(tmp_path)
    for m in (3, 4, 5):
        _close_with_snapshot(
            db, 2026, m,
            actuals=[{"customer": "B", "product": "P2", "qty": 130, "amount": 1300}],
            forecasts=[{"customer": "B", "product": "P2", "fcst": 100}],
        )
    bias = build_forecast_bias(db, 2026, 5, lookback=3)
    under = [r for r in bias.under_forecast if (r.customer_name, r.product_code) == ("B", "P2")]
    assert under and under[0].direction == "under"
    assert abs(under[0].avg_accuracy - 1.3) < 1e-6


def test_steady_forecast_not_flagged(tmp_path):
    db = _db(tmp_path)
    # ratio fluctuates around 1 — should not exceed threshold
    for m, qty in zip((3, 4, 5), (105, 95, 100)):
        _close_with_snapshot(
            db, 2026, m,
            actuals=[{"customer": "C", "product": "P3", "qty": qty, "amount": qty * 10}],
            forecasts=[{"customer": "C", "product": "P3", "fcst": 100}],
        )
    bias = build_forecast_bias(db, 2026, 5, lookback=3)
    flagged = [
        r for r in (bias.over_forecast + bias.under_forecast)
        if (r.customer_name, r.product_code) == ("C", "P3")
    ]
    assert flagged == []


def test_pack_quantity_does_not_create_false_over_forecast_bias(tmp_path):
    db = _db(tmp_path)
    _set_price_quantity(db, "P4", 280)
    _close_with_snapshot(
        db, 2026, 5,
        actuals=[{"customer": "D", "product": "P4", "qty": 10, "amount": 2800}],
        forecasts=[{"customer": "D", "product": "P4", "fcst": 2800}],
    )

    bias = build_forecast_bias(db, 2026, 5, lookback=1)

    assert bias.over_forecast == []
    assert bias.under_forecast == []
