from datetime import date

from src.backend.forecast_models import ForecastRow
from src.backend.product_monitor_rows import build_product_monitor_rows


def _row() -> ForecastRow:
    return ForecastRow(
        row_id="A__P1",
        customer="A",
        product_code="P1",
        product_name="Product One",
        latest_order_date=date(2026, 4, 20),
        cycle_days=30,
        next_order_date=None,
        auto_in_month=False,
        last_year_same_month_qty=100,
        this_year_same_month_qty=30,
        latest_price=100,
        system_forecast=80,
        manual_adjustment=None,
        final_forecast=80,
        estimated_amount=8000,
        forecast_basis="data_driven",
        budget_quantity=100,
    )


def test_build_product_monitor_rows_uses_injected_amount_calculator():
    rows = build_product_monitor_rows(
        [_row()],
        amount_for_quantity=lambda quantity, _row: quantity * 5,
    )

    assert rows[0].diff_quantity == -20
    assert rows[0].amount_impact == -100
