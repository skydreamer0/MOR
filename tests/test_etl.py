import tempfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from src.backend.etl import normalize_budget_targets


def test_normalize_budget_targets_keeps_quantity_and_amount_formats_separate():
    df = pd.DataFrame(
        [
            {"客戶簡稱": "A", "商品號": "P1", "年": 2026, "標  題": "02預算總量", 5: 2},
            {"客戶簡稱": "A", "商品號": "P1", "年": 2026, "標  題": "04預算總額", 5: 1000},
            {"客戶簡稱": "A", "商品號": "P1", "年": 2026, "標  題": "05金達成率", 5: 75},
            {"客戶簡稱": "A", "商品號": "P1", "年": 2026, "標  題": "07預算S總量", 5: 20},
            {"客戶簡稱": "B", "商品號": 1002, "年": 2026, "標  題": "07預算S總量", 5: 3},
        ]
    )

    rows = normalize_budget_targets(df, default_year=2026)
    by_key = {
        (row.customer_name, row.product_code, row.month): row
        for row in rows.itertuples(index=False)
    }

    assert by_key[("A", "P1", 5)].target_quantity == 20
    assert by_key[("A", "P1", 5)].base_target_quantity == 2
    assert by_key[("A", "P1", 5)].target_amount == 1000
    assert by_key[("B", "1002", 5)].target_quantity == 3


def test_sync_cleanup_failure_does_not_propagate(tmp_path):
    """cleanup failure is best-effort: sync_excel_to_db must not raise."""
    from src.backend.database import MORDatabase
    from src.backend.etl import sync_excel_to_db

    db = MORDatabase(tmp_path / "test.db")
    fake_sales = pd.DataFrame([{
        "order_date": pd.Timestamp("2026-05-31"),
        "customer_name": "X",
        "product_code": "Y",
        "product_name": "Test",
        "quantity": 1,
        "unit_price": 100.0,
        "amount": 100.0,
    }])

    with patch("src.backend.etl._find_first_file") as mock_find, \
         patch("src.backend.etl.pd.read_excel", return_value=pd.DataFrame()), \
         patch("src.backend.etl.normalize_sales_records", return_value=fake_sales), \
         patch("src.backend.etl._clear_covered_current_month_records", side_effect=RuntimeError("boom")):
        mock_find.side_effect = lambda root, pattern: (
            root / "fake.xlsx" if "業績" in pattern else None
        )
        sync_excel_to_db(db, tmp_path)  # must not raise

    with db.get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM sales_records").fetchone()[0]
    assert count == 1


def test_normalize_budget_targets_uses_default_year_when_sheet_has_no_year_column():
    df = pd.DataFrame([
        {"客戶簡稱": "A", "商品號": "P1", "標  題": "07預算S總量", 5: 20},
    ])

    rows = normalize_budget_targets(df, default_year=2027)

    assert rows.iloc[0]["year"] == 2027


def test_sync_excel_to_db_infers_budget_year_from_latest_budget_filename(tmp_path):
    from src.backend.database import MORDatabase
    from src.backend.etl import sync_excel_to_db

    db = MORDatabase(tmp_path / "test.db")
    sales = pd.DataFrame([
        {"年": 2027, "月": 5, "日": 1, "客戶簡稱": "A", "商品號": "P1", "商品簡稱": "Product", "銷+贈S量": 1, "單價NT(淨)": 10, "含稅總額(淨)": 10},
    ])
    budget = pd.DataFrame([
        {"客戶簡稱": "A", "商品號": "P1", "標  題": "07預算S總量", 5: 20},
    ])
    sales.to_excel(tmp_path / "業績明細.xlsx", index=False, sheet_name="業績明細")
    budget.to_excel(tmp_path / "2027預算報表.xlsx", index=False)

    sync_excel_to_db(db, tmp_path)

    with db.get_connection() as conn:
        saved = conn.execute(
            "SELECT year, month, target_quantity FROM budget_targets"
        ).fetchone()

    assert tuple(saved) == (2027, 5, 20.0)


def test_sync_excel_to_db_prefers_requested_budget_year(tmp_path):
    from src.backend.database import MORDatabase
    from src.backend.etl import sync_excel_to_db

    db = MORDatabase(tmp_path / "test.db")
    sales = pd.DataFrame([
        {"年": 2027, "月": 5, "日": 1, "客戶簡稱": "A", "商品號": "P1", "商品簡稱": "Product", "銷+贈S量": 1, "單價NT(淨)": 10, "含稅總額(淨)": 10},
    ])
    budget_2026 = pd.DataFrame([{ "客戶簡稱": "A", "商品號": "P1", "標  題": "07預算S總量", 5: 10 }])
    budget_2027 = pd.DataFrame([{ "客戶簡稱": "A", "商品號": "P1", "標  題": "07預算S總量", 5: 20 }])
    sales.to_excel(tmp_path / "業績明細.xlsx", index=False, sheet_name="業績明細")
    budget_2026.to_excel(tmp_path / "2026預算報表.xlsx", index=False)
    budget_2027.to_excel(tmp_path / "2027預算報表.xlsx", index=False)

    sync_excel_to_db(db, tmp_path, default_budget_year=2026)

    with db.get_connection() as conn:
        saved = conn.execute(
            "SELECT year, month, target_quantity FROM budget_targets"
        ).fetchone()

    assert tuple(saved) == (2026, 5, 10.0)


def test_sync_excel_to_db_ignores_legacy_excluded_items_json(tmp_path):
    from src.backend.database import MORDatabase
    from src.backend.etl import sync_excel_to_db

    db = MORDatabase(tmp_path / "test.db")
    sales = pd.DataFrame([
        {
            "年": 2027, "月": 5, "日": 1, "客戶簡稱": "A",
            "商品號": "P1", "商品簡稱": "Product", "銷+贈S量": 1,
            "單價NT(淨)": 10, "含稅總額(淨)": 10,
        },
    ])
    sales.to_excel(tmp_path / "業績明細.xlsx", index=False, sheet_name="業績明細")
    (tmp_path / "excluded_items.json").write_text('["P1"]', encoding="utf-8")

    sync_excel_to_db(db, tmp_path)

    with db.get_connection() as conn:
        migrated = conn.execute(
            "SELECT is_excluded FROM item_configs WHERE product_code = 'P1'"
        ).fetchone()

    assert migrated is None
