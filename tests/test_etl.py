import pandas as pd

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
