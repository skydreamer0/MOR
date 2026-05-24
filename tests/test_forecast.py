from datetime import date

import pandas as pd

from src.backend.forecast_config import ForecastConfig
from src.backend.forecast_engine import ForecastOptions, ForecastTarget, apply_user_adjustments, build_forecast
from src.backend.row_identity import make_row_id


def sample_sales_data() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"年": 2026, "月": 1, "日": 10, "客戶簡稱": "A客戶", "商品號": "P1", "商品簡稱": "商品A", "銷+贈S量": 10, "單價NT(淨)": 100, "含稅總額(淨)": 1050},
            {"年": 2026, "月": 2, "日": 10, "客戶簡稱": "A客戶", "商品號": "P1", "商品簡稱": "商品A", "銷+贈S量": 14, "單價NT(淨)": 110, "含稅總額(淨)": 1617},
            {"年": 2026, "月": 3, "日": 10, "客戶簡稱": "A客戶", "商品號": "P1", "商品簡稱": "商品A", "銷+贈S量": 16, "單價NT(淨)": 120, "含稅總額(淨)": 2016},
            {"年": 2025, "月": 4, "日": 10, "客戶簡稱": "A客戶", "商品號": "P1", "商品簡稱": "商品A", "銷+贈S量": 8, "單價NT(淨)": 90, "含稅總額(淨)": 756},
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
    # Last-year same-month quantity is for risk comparison only.
    # Forecast uses recent history sources: last month and recent 3-month average.
    expected_qty = (16 + 40 / 3) / 2
    assert summary.total == expected_qty * 120
    assert len(summary.rows) == 1

    row = summary.rows[0]
    assert row.customer == "A客戶"
    assert row.product_code == "P1"
    assert row.latest_price == 120
    assert abs(row.system_forecast - expected_qty) < 1e-8
    assert abs(row.estimated_amount - expected_qty * 120) < 1e-8
    assert row.forecast_basis == "data_driven"
    assert row.next_order_date == date(2026, 4, 9)
    assert row.last_year_same_month_qty == 8


def test_user_adjustments_override_quantity_and_exclusion_removes_amount():
    summary = build_forecast(sample_sales_data(), ForecastTarget(2026, 4))

    adjusted = apply_user_adjustments(summary, manual_adjustments={summary.rows[0].row_id: 5}, excluded_ids=set())

    assert adjusted.rows[0].final_forecast == 5
    assert adjusted.rows[0].estimated_amount == 600
    assert adjusted.total == 600

    excluded = apply_user_adjustments(adjusted, manual_adjustments={}, excluded_ids={summary.rows[0].row_id})

    assert excluded.rows[0].excluded is True
    assert excluded.rows[0].estimated_amount == 0
    assert excluded.total == 0


def test_excluded_item_ids_match_numeric_excel_product_codes():
    data = sample_sales_data().assign(**{"商品號": 1001})

    summary = build_forecast(
        data,
        ForecastTarget(2026, 4),
        ForecastOptions(
            include_all=True,
            excluded_item_ids={"1001"},
            max_cycle_interval_days=ForecastConfig().max_cycle_interval_days,
        ),
    )

    assert summary.rows[0].product_code == "1001"
    assert summary.rows[0].excluded is True
    assert summary.rows[0].estimated_amount == 0
    assert summary.total == 0


def test_build_forecast_uses_canonical_row_identity_for_delimiter_values():
    data = sample_sales_data()
    data.iloc[:, 3] = "A__B"
    data.iloc[:, 4] = "C"

    summary = build_forecast(
        data,
        ForecastTarget(2026, 4),
        ForecastOptions(include_all=True, max_cycle_interval_days=ForecastConfig().max_cycle_interval_days),
    )

    assert summary.rows[0].row_id == make_row_id("A__B", "C")
