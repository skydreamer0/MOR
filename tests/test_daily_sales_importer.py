from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest

from src.backend.database import MORDatabase


def test_daily_sales_tables_are_initialized(tmp_path: Path):
    db = MORDatabase(tmp_path / "mor_workbench.db")

    with db.get_connection() as conn:
        batch_cols = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(daily_import_batches)").fetchall()
        }
        actual_cols = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(daily_sales_actuals)").fetchall()
        }

    assert {
        "id", "source_filename", "source_hash", "sales_year", "sales_month",
        "imported_at", "row_count", "date_start", "date_end",
        "quantity_total", "taxed_amount_total", "status", "message",
    }.issubset(batch_cols)
    assert {
        "id", "sales_year", "sales_month", "sales_date", "customer_code",
        "customer_name", "product_code", "product_name", "sales_quantity",
        "gift_quantity", "actual_quantity", "net_unit_price", "taxed_amount",
        "bonus_basis_amount", "invoice_number", "shipment_number",
        "order_type", "performance_type", "import_batch_id",
    }.issubset(actual_cols)


# ---------------------------------------------------------------------------
# Helpers shared across tasks 3–4
# ---------------------------------------------------------------------------

def _workbook_bytes(rows: list[dict]) -> BytesIO:
    stream = BytesIO()
    pd.DataFrame(rows).to_excel(stream, index=False)
    stream.seek(0)
    return stream


def _daily_row(date: str, customer: str, product: str, qty: float, taxed_amount: float) -> dict:
    return {
        "出貨日期": date,
        "客戶代號": "C001",
        "客戶簡稱": customer,
        "產品": product,
        "產品簡稱": "Product",
        "銷售數量": qty,
        "贈品數量": 0,
        "銷貨淨價": taxed_amount / qty if qty else 0,
        "含稅淨額": taxed_amount,
        "折後業績": 0,
        "發票編號": "INV",
        "出貨單號": "SHIP",
        "單別": "正常銷",
        "業績屬性": "處方",
    }


# ---------------------------------------------------------------------------
# Task 2: normalize_daily_sales
# ---------------------------------------------------------------------------

from src.backend.daily_sales_importer import normalize_daily_sales


def test_normalize_daily_sales_ignores_summary_rows_and_computes_quantity():
    raw = pd.DataFrame(
        [
            {
                "出貨日期": "2026-05-04",
                "客戶代號": "HIN231001R",
                "客戶簡稱": "耕莘台北",
                "產品": "T5EL1",
                "產品簡稱": "ELI 22.5癌立佳",
                "銷售數量": 5,
                "贈品數量": 1,
                "銷貨淨價": 5309.2,
                "含稅淨額": 26546,
                "折後業績": 25282,
                "發票編號": "BC59676516",
                "出貨單號": "1A8101934077",
                "單別": "正常銷",
                "業績屬性": "處方",
            },
            {
                "出貨日期": None,
                "客戶代號": None,
                "客戶簡稱": None,
                "產品": None,
                "產品簡稱": "每日總計",
                "銷售數量": 999,
                "贈品數量": 0,
                "銷貨淨價": 0,
                "含稅淨額": 999,
                "折後業績": 999,
                "發票編號": None,
                "出貨單號": None,
                "單別": None,
                "業績屬性": None,
            },
        ]
    )

    rows = normalize_daily_sales(raw)

    assert len(rows) == 1
    row = rows.iloc[0]
    assert row.sales_year == 2026
    assert row.sales_month == 5
    assert row.customer_name == "耕莘台北"
    assert row.product_code == "T5EL1"
    assert row.actual_quantity == 6
    assert row.taxed_amount == 26546
    assert row.bonus_basis_amount == 25282


# ---------------------------------------------------------------------------
# Task 3: import_daily_sales_workbook — same-month overwrite
# ---------------------------------------------------------------------------

from src.backend.daily_sales_importer import import_daily_sales_workbook


def test_import_daily_sales_workbook_overwrites_same_month(tmp_path: Path):
    db = MORDatabase(tmp_path / "mor_workbench.db")

    first = _workbook_bytes([_daily_row("2026-05-04", "Hospital A", "P1", 5, 1000)])
    second = _workbook_bytes([_daily_row("2026-05-08", "Hospital A", "P1", 9, 1800)])

    import_daily_sales_workbook(db, first, "first.xlsx")
    result = import_daily_sales_workbook(db, second, "second.xlsx")

    with db.get_connection() as conn:
        rows = conn.execute("SELECT * FROM daily_sales_actuals").fetchall()
        batches = conn.execute("SELECT * FROM daily_import_batches ORDER BY id").fetchall()

    assert result.sales_year == 2026
    assert result.sales_month == 5
    assert result.row_count == 1
    assert len(batches) == 2
    assert len(rows) == 1
    assert rows[0]["actual_quantity"] == 9
    assert rows[0]["taxed_amount"] == 1800


# ---------------------------------------------------------------------------
# Task 4: fetch_daily_actuals_by_row_id
# ---------------------------------------------------------------------------

from src.backend.daily_sales_importer import fetch_daily_actuals_by_row_id


def test_fetch_daily_actuals_by_row_id_aggregates_quantity_and_latest_date(tmp_path: Path):
    db = MORDatabase(tmp_path / "mor_workbench.db")
    stream = _workbook_bytes(
        [
            _daily_row("2026-05-04", "Hospital A", "P1", 5, 1000),
            _daily_row("2026-05-08", "Hospital A", "P1", 2, 400),
        ]
    )

    import_daily_sales_workbook(db, stream, "daily.xlsx")
    actuals = fetch_daily_actuals_by_row_id(db, 2026, 5)

    row = actuals["Hospital A__P1"]
    assert row.actual_quantity == 7
    assert row.taxed_amount == 1400
    assert str(row.latest_sales_date) == "2026-05-08"


def test_fetch_daily_actuals_by_row_id_uses_canonical_row_identity(tmp_path: Path):
    from src.backend.row_identity import make_row_id

    db = MORDatabase(tmp_path / "mor_workbench.db")
    stream = _workbook_bytes(
        [
            _daily_row("2026-05-04", "A__B", "C", 5, 1000),
            _daily_row("2026-05-05", "A", "B__C", 2, 400),
        ]
    )

    import_daily_sales_workbook(db, stream, "daily.xlsx")
    actuals = fetch_daily_actuals_by_row_id(db, 2026, 5)

    assert set(actuals) == {make_row_id("A__B", "C"), make_row_id("A", "B__C")}


# ---------------------------------------------------------------------------
# Phase 6: close_month / is_month_closed / guard on import
# ---------------------------------------------------------------------------

from src.backend.daily_sales_importer import (
    close_month,
    get_close_record,
    get_latest_import_batch,
    is_month_closed,
)


def test_is_month_closed_false_before_close(tmp_path: Path):
    db = MORDatabase(tmp_path / "mor_workbench.db")
    assert is_month_closed(db, 2026, 5) is False


def test_close_month_creates_record(tmp_path: Path):
    db = MORDatabase(tmp_path / "mor_workbench.db")
    stream = _workbook_bytes([_daily_row("2026-05-04", "Hospital A", "P1", 10, 2000)])
    import_daily_sales_workbook(db, stream, "may.xlsx")

    close_month(db, 2026, 5)

    assert is_month_closed(db, 2026, 5) is True
    rec = get_close_record(db, 2026, 5)
    assert rec is not None
    assert rec["actual_row_count"] == 1
    assert rec["actual_quantity_total"] == 10
    assert rec["actual_amount_total"] == 2000


def test_close_month_raises_when_already_closed(tmp_path: Path):
    db = MORDatabase(tmp_path / "mor_workbench.db")
    stream = _workbook_bytes([_daily_row("2026-05-04", "H", "P1", 5, 1000)])
    import_daily_sales_workbook(db, stream, "may.xlsx")
    close_month(db, 2026, 5)

    with pytest.raises(ValueError, match="已結月"):
        close_month(db, 2026, 5)


def test_close_month_raises_when_no_data(tmp_path: Path):
    db = MORDatabase(tmp_path / "mor_workbench.db")
    with pytest.raises(ValueError, match="尚無匯入資料"):
        close_month(db, 2026, 5)


def test_import_blocked_after_close(tmp_path: Path):
    db = MORDatabase(tmp_path / "mor_workbench.db")
    stream = _workbook_bytes([_daily_row("2026-05-04", "H", "P1", 5, 1000)])
    import_daily_sales_workbook(db, stream, "may.xlsx")
    close_month(db, 2026, 5)

    new_stream = _workbook_bytes([_daily_row("2026-05-10", "H", "P1", 8, 1600)])
    with pytest.raises(ValueError, match="已結月"):
        import_daily_sales_workbook(db, new_stream, "may_v2.xlsx")


def test_get_latest_import_batch_returns_most_recent(tmp_path: Path):
    db = MORDatabase(tmp_path / "mor_workbench.db")
    first = _workbook_bytes([_daily_row("2026-05-04", "H", "P1", 5, 1000)])
    second = _workbook_bytes([_daily_row("2026-05-08", "H", "P1", 9, 1800)])
    import_daily_sales_workbook(db, first, "first.xlsx")
    import_daily_sales_workbook(db, second, "second.xlsx")

    batch = get_latest_import_batch(db, 2026, 5)
    assert batch is not None
    assert batch["source_filename"] == "second.xlsx"
    assert batch["row_count"] == 1
