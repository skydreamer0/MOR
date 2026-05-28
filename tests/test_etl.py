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
