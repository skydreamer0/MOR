from datetime import date

import pandas as pd

from src.backend.dashboard_analytics_workflow import build_dashboard_template_context
from src.backend.forecast_models import ForecastRow, ForecastSummary, ForecastTarget
from src.backend.forecast_workbench_context import ForecastPageContext
from src.backend.dashboard_metrics import DashboardMetrics
from src.backend.data_health_summary import DataHealthSummary
from src.backend.product_monitor_rows import ProductMonitorRow


def _row(row_id: str, customer: str, product_code: str, product_name: str, amount: float) -> ForecastRow:
    monthly_amounts = [0.0] * 12
    monthly_amounts[4] = amount
    return ForecastRow(
        row_id=row_id,
        customer=customer,
        product_code=product_code,
        product_name=product_name,
        latest_order_date=date(2026, 4, 20),
        cycle_days=30,
        next_order_date=date(2026, 5, 20),
        auto_in_month=True,
        last_year_same_month_qty=100,
        this_year_same_month_qty=20,
        latest_price=10,
        system_forecast=80,
        manual_adjustment=None,
        final_forecast=80,
        estimated_amount=amount,
        forecast_basis="data_driven",
        ly_monthly_amount=monthly_amounts,
        ty_monthly_amount=monthly_amounts,
        budget_monthly_amount=monthly_amounts,
    )


def _monitor(customer: str, status_key: str, amount_impact: float) -> ProductMonitorRow:
    return ProductMonitorRow(
        customer=customer,
        product_code=f"{customer}-{status_key}",
        product_name=f"{customer} {status_key}",
        last_year_quantity=100,
        last_month_quantity=80,
        current_quantity=20,
        forecast_quantity=70,
        diff_quantity=-30,
        drop_rate=-0.3,
        status=status_key,
        status_key=status_key,
        note="",
        amount_impact=amount_impact,
    )


def test_build_dashboard_template_context_preserves_dashboard_analytics_contract():
    rows = [
        _row("A__P1", "Customer A", "P1", "Product One", 800),
        _row("B__P2", "Customer B", "P2", "Product Two", 400),
    ]
    context = ForecastPageContext(
        target=ForecastTarget(2026, 5),
        sales_data=pd.DataFrame(),
        summary=ForecastSummary(year=2026, month=5, rows=rows, total=1200),
        dashboard=DashboardMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        monitor_rows=[
            _monitor("Customer A", "high", -300),
            _monitor("Customer B", "caution", -500),
            _monitor("Customer C", "high", -700),
            _monitor("Customer D", "ok", 0),
        ],
        health=DataHealthSummary(
            order_count=2,
            order_start=date(2026, 4, 1),
            order_end=date(2026, 4, 20),
            budget_month_count=1,
            budget_months=[(2026, 5)],
            missing_budget_row_count=0,
            zero_price_row_count=0,
            no_last_year_row_count=0,
        ),
        items=[],
    )

    template_context = build_dashboard_template_context(context, today=date(2026, 5, 10))

    assert template_context["year"] == 2026
    assert template_context["month"] == 5
    assert template_context["metrics"] is context.dashboard
    assert template_context["health"] is context.health
    assert template_context["remaining_days"] == 21
    assert template_context["status_dist"] == {"high": 2, "caution": 1, "ok": 1, "no_history": 0}
    assert [row.customer for row in template_context["monitor_rows"]] == ["Customer C", "Customer A"]
    assert [item.customer for item in template_context["customer_ranking"]] == ["Customer C", "Customer B", "Customer A"]
    assert template_context["data_issues"] == []
    assert template_context["analytics_total"][0]["entity_type"] == "total"
    assert {item["entity_id"] for item in template_context["analytics_customers"]} == {"Customer A", "Customer B"}
    assert {item["entity_id"] for item in template_context["analytics_products"]} == {"P1", "P2"}
