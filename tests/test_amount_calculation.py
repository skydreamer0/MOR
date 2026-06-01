from dataclasses import replace
from datetime import date

from src.backend.forecast_models import ForecastRow


def _row(**overrides) -> ForecastRow:
    row = ForecastRow(
        row_id="A__P1",
        customer="A",
        product_code="P1",
        product_name="Product",
        latest_order_date=date(2026, 4, 20),
        cycle_days=30,
        next_order_date=date(2026, 5, 20),
        auto_in_month=True,
        last_year_same_month_qty=100,
        this_year_same_month_qty=20,
        latest_price=3200,
        system_forecast=250,
        manual_adjustment=None,
        final_forecast=250,
        estimated_amount=0,
        forecast_basis="data_driven",
        budget_quantity=280,
        budget_amount=2800,
        base_budget_quantity=1,
    )
    return replace(row, **overrides)


def test_amount_for_quantity_scales_by_latest_price_quantity():
    from src.backend.amount_calculation import amount_for_quantity

    assert amount_for_quantity(250, _row()) == 250 / 280 * 3200


def test_forecast_row_amount_excludes_unbudgeted_and_excluded_rows():
    from src.backend.amount_calculation import forecast_row_amount, is_amount_included

    budgeted = _row()
    unbudgeted = _row(budget_quantity=0, base_budget_quantity=0)
    excluded = _row(excluded=True)

    assert is_amount_included(budgeted) is True
    assert forecast_row_amount(budgeted) == 250 / 280 * 3200
    assert is_amount_included(unbudgeted) is False
    assert forecast_row_amount(unbudgeted) == 0
    assert is_amount_included(excluded) is False
    assert forecast_row_amount(excluded) == 0


# ---------------------------------------------------------------------------
# Monthly review helpers
# ---------------------------------------------------------------------------

def test_period_avg_unit_price_basic():
    from src.backend.amount_calculation import period_avg_unit_price
    assert period_avg_unit_price(100, 8500) == 85.0


def test_period_avg_unit_price_zero_quantity_returns_zero():
    from src.backend.amount_calculation import period_avg_unit_price
    assert period_avg_unit_price(0, 5000) == 0.0


def test_review_forecast_amount_uses_period_price_when_available():
    from src.backend.amount_calculation import review_forecast_amount
    assert review_forecast_amount(90, period_unit_price=85, fallback_unit_price=80) == 90 * 85


def test_review_forecast_amount_falls_back_when_period_price_missing():
    from src.backend.amount_calculation import review_forecast_amount
    assert review_forecast_amount(90, period_unit_price=0, fallback_unit_price=80) == 90 * 80


def test_review_forecast_amount_returns_zero_when_no_price():
    from src.backend.amount_calculation import review_forecast_amount
    assert review_forecast_amount(90, period_unit_price=0, fallback_unit_price=0) == 0
