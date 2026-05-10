from dataclasses import replace
from datetime import date

from src.backend.forecast_models import ForecastRow, ForecastSummary
from src.backend.web.forecast_presenter import column_schema, product_display_name, serialize_summary


def sample_summary() -> ForecastSummary:
    return ForecastSummary(
        year=2026,
        month=5,
        total=1200,
        rows=[
            ForecastRow(
                row_id="customer-product",
                customer="台北醫院",
                product_code="P1",
                product_name="商品A",
                latest_order_date=date(2026, 4, 10),
                cycle_days=30,
                next_order_date=date(2026, 5, 10),
                auto_in_month=True,
                last_year_same_month_qty=8,
                this_year_same_month_qty=4,
                latest_price=120,
                system_forecast=10,
                manual_adjustment=None,
                final_forecast=10,
                estimated_amount=1200,
                forecast_basis="cycle",
                excluded=False,
            )
        ],
    )


def test_serialize_summary_returns_json_safe_dates_and_counts():
    payload = serialize_summary(sample_summary())

    assert payload["target"] == {"year": 2026, "month": 5}
    assert payload["summary"] == {
        "total": 1200,
        "row_count": 1,
        "auto_row_count": 1,
        "included_count": 1,
        "excluded_count": 0,
    }
    assert payload["rows"][0]["latest_order_date"] == "2026-04-10"
    assert payload["rows"][0]["next_order_date"] == "2026-05-10"
    assert payload["rows"][0]["customer"] == "台北醫院"


def test_serialize_summary_compares_forecast_gap_to_budget():
    summary = sample_summary()
    row = replace(summary.rows[0], budget_quantity=7)
    payload = serialize_summary(replace(summary, rows=[row]))

    assert payload["rows"][0]["achievement_rate"] == 10 / 7 * 100
    assert payload["rows"][0]["diff"] == 3


def test_column_schema_describes_review_grid_fields():
    schema = column_schema()

    status = next(column for column in schema if column["key"] == "auto_in_month")
    manual_adjustment = next(column for column in schema if column["key"] == "manual_adjustment")
    amount = next(column for column in schema if column["key"] == "estimated_amount")

    assert status["key"] == "auto_in_month"
    assert status["type"] == "status"
    assert manual_adjustment["label"] == "人工調整"
    assert manual_adjustment["editable"] is True
    assert amount["align"] == "right"


def test_product_display_name_keeps_three_chars_except_eli_dose():
    assert product_display_name("商品ABC") == "商品A"
    assert product_display_name("ELI 22.5癌立佳") == "ELI 22.5"
    assert product_display_name("ELI7.5癌立佳") == "ELI 7.5"
    assert product_display_name("ＥＬＩ 7.5癌立佳") == "ＥＬＩ 7.5"
