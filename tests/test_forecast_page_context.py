from __future__ import annotations

from datetime import date

import pytest

from src.backend.forecast_models import ForecastRow, ForecastSummary
from src.backend.forecast_page_context import (
    build_forecast_page_render_context,
    forecast_signature,
    validate_forecast_signature,
)


def _row(
    row_id: str,
    customer: str,
    product_code: str,
    *,
    last_year_qty: float,
    final_qty: float,
    amount: float,
    item_status: str = "active",
) -> ForecastRow:
    return ForecastRow(
        row_id=row_id,
        customer=customer,
        product_code=product_code,
        product_name=f"Product {product_code}",
        latest_order_date=date(2026, 4, 1),
        cycle_days=30,
        next_order_date=date(2026, 5, 1),
        auto_in_month=True,
        last_year_same_month_qty=last_year_qty,
        this_year_same_month_qty=0,
        latest_price=10,
        system_forecast=final_qty,
        manual_adjustment=None,
        final_forecast=final_qty,
        estimated_amount=amount,
        forecast_basis="data_driven",
        budget_quantity=1,
        item_status=item_status,
        ly_monthly_amount=[amount] * 12,
    )


def test_build_forecast_page_render_context_preserves_route_presentation_rules():
    summary = ForecastSummary(
        year=2026,
        month=5,
        total=3300,
        rows=[
            _row("B__P2", "B", "P2", last_year_qty=100, final_qty=95, amount=1000),
            _row("A__P1", "A", "P1", last_year_qty=100, final_qty=50, amount=500),
            _row("C__P3", "C", "P3", last_year_qty=100, final_qty=100, amount=1200, item_status="discontinued"),
            _row("A__P4", "A", "P4", last_year_qty=0, final_qty=10, amount=600),
        ],
    )

    context = build_forecast_page_render_context(summary, visible_row_limit=2)

    assert [row.row_id for row in context.rows] == ["A__P1", "A__P4"]
    assert [row.row_id for row in context.discontinued_rows] == ["C__P3"]
    assert context.discontinued_last_year_total == 1000
    assert context.unrendered_total == 2700
    assert context.row_count == 4
    assert context.shown_count == 3
    assert context.customers == ["A"]
    assert context.risk_levels == {"A__P1": "high", "A__P4": "normal", "C__P3": "normal"}
    assert context.forecast_signature == forecast_signature(summary)


def test_build_forecast_page_render_context_returns_empty_fallback_without_summary():
    context = build_forecast_page_render_context(
        None,
        visible_row_limit=50,
        fallback_year="bad-year",
        fallback_month="bad-month",
    )

    assert context.year == "bad-year"
    assert context.month == "bad-month"
    assert context.rows == []
    assert context.discontinued_rows == []
    assert context.forecast_signature == ""
    assert context.risk_levels == {}


def test_validate_forecast_signature_allows_empty_signature_for_legacy_export_posts():
    summary = ForecastSummary(
        year=2026,
        month=5,
        total=500,
        rows=[_row("A__P1", "A", "P1", last_year_qty=100, final_qty=50, amount=500)],
    )

    validate_forecast_signature(summary, "")


def test_validate_forecast_signature_rejects_stale_signature():
    summary = ForecastSummary(
        year=2026,
        month=5,
        total=500,
        rows=[_row("A__P1", "A", "P1", last_year_qty=100, final_qty=50, amount=500)],
    )

    with pytest.raises(ValueError, match="Forecast review changed"):
        validate_forecast_signature(summary, "stale")
