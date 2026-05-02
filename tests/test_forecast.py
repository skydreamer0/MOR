from datetime import date

import pandas as pd

from forecast_config import ForecastConfig
from forecast_engine import ForecastOptions, ForecastTarget, apply_user_adjustments, build_forecast


def sample_sales_data() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"年": 2026, "月": 1, "日": 10, "客戶簡稱": "A客戶", "商品號": "P1", "商品簡稱": "商品A", "銷+贈S量": 10, "單價NT(淨)": 100},
            {"年": 2026, "月": 2, "日": 10, "客戶簡稱": "A客戶", "商品號": "P1", "商品簡稱": "商品A", "銷+贈S量": 14, "單價NT(淨)": 110},
            {"年": 2026, "月": 3, "日": 10, "客戶簡稱": "A客戶", "商品號": "P1", "商品簡稱": "商品A", "銷+贈S量": 16, "單價NT(淨)": 120},
            {"年": 2025, "月": 4, "日": 10, "客戶簡稱": "A客戶", "商品號": "P1", "商品簡稱": "商品A", "銷+贈S量": 8, "單價NT(淨)": 90},
        ]
    )


def test_build_forecast_returns_summary_with_typed_rows():
    summary = build_forecast(
        sample_sales_data(),
        ForecastTarget(2026, 4),
        ForecastOptions(include_all=False, max_cycle_interval_days=ForecastConfig().max_cycle_interval_days),
    )

    assert summary.year == 2026
    assert summary.month == 4
    assert summary.total == (40 / 3) * 120
    assert len(summary.rows) == 1

    row = summary.rows[0]
    assert row.customer == "A客戶"
    assert row.product_code == "P1"
    assert row.latest_price == 120
    assert row.forecast_quantity == 40 / 3
    assert row.estimated_amount == (40 / 3) * 120
    assert row.forecast_basis == "cycle"
    assert row.next_order_date == date(2026, 4, 9)
    assert row.last_year_same_month_qty == 8


def test_user_adjustments_override_quantity_and_exclusion_removes_amount():
    summary = build_forecast(sample_sales_data(), ForecastTarget(2026, 4))

    adjusted = apply_user_adjustments(summary, manual_quantities={summary.rows[0].row_id: 5}, excluded_ids=set())

    assert adjusted.rows[0].effective_quantity == 5
    assert adjusted.rows[0].estimated_amount == 600
    assert adjusted.total == 600

    excluded = apply_user_adjustments(adjusted, manual_quantities={}, excluded_ids={summary.rows[0].row_id})

    assert excluded.rows[0].excluded is True
    assert excluded.rows[0].estimated_amount == 0
    assert excluded.total == 0
