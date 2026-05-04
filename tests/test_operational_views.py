from dataclasses import replace
from datetime import date

import pandas as pd

from src.backend.forecast_models import ForecastRow, ForecastSummary
from src.backend.operational_views import (
    build_dashboard_metrics,
    build_data_health_summary,
    build_product_monitor_rows,
)


def _row(
    *,
    row_id: str,
    customer: str,
    product_code: str,
    product_name: str,
    last_year: float,
    last_month: float,
    current: float,
    final: float,
    budget: float,
    price: float,
    budget_amount: float = 0,
    reason: str | None = None,
) -> ForecastRow:
    return ForecastRow(
        row_id=row_id,
        customer=customer,
        product_code=product_code,
        product_name=product_name,
        latest_order_date=date(2026, 4, 20),
        cycle_days=30,
        next_order_date=date(2026, 5, 20),
        auto_in_month=True,
        last_year_same_month_qty=last_year,
        this_year_same_month_qty=current,
        latest_price=price,
        system_forecast=final,
        manual_adjustment=None,
        final_forecast=final,
        estimated_amount=final * price,
        forecast_basis="data_driven",
        adjustment_reason=reason,
        budget_quantity=budget,
        budget_amount=budget_amount,
        last_month_actual=last_month,
        last_month_budget=budget,
        excluded=False,
    )


def test_dashboard_metrics_summarize_quantity_amount_and_high_risk_counts():
    rows = [
        _row(
            row_id="A__P1",
            customer="A",
            product_code="P1",
            product_name="Alpha",
            last_year=100,
            last_month=80,
            current=20,
            final=80,
            budget=120,
            price=10,
            budget_amount=1500,
        ),
        _row(
            row_id="B__P1",
            customer="B",
            product_code="P1",
            product_name="Alpha",
            last_year=50,
            last_month=60,
            current=30,
            final=60,
            budget=40,
            price=20,
            budget_amount=900,
        ),
        _row(
            row_id="C__P2",
            customer="C",
            product_code="P2",
            product_name="Beta",
            last_year=0,
            last_month=0,
            current=5,
            final=5,
            budget=10,
            price=30,
        ),
        _row(
            row_id="D__P3",
            customer="D",
            product_code="P3",
            product_name="Unbudgeted",
            last_year=0,
            last_month=0,
            current=999,
            final=999,
            budget=0,
            price=999,
        ),
    ]

    metrics = build_dashboard_metrics(rows)

    assert metrics.target_quantity == 170
    assert metrics.target_amount == 2700
    assert metrics.actual_quantity == 55
    assert metrics.actual_amount == 1075
    assert metrics.forecast_quantity == 145
    assert metrics.forecast_amount == 2500
    assert metrics.quantity_gap == -25
    assert metrics.amount_gap == -200
    assert metrics.achievement_rate == 145 / 170 * 100
    assert metrics.high_risk_product_count == 1
    assert metrics.high_risk_customer_count == 1


def test_product_monitor_rows_classify_yoy_drop_statuses_and_notes():
    rows = [
        _row(
            row_id="A__P1",
            customer="A",
            product_code="P1",
            product_name="High Risk",
            last_year=100,
            last_month=80,
            current=20,
            final=89,
            budget=90,
            price=10,
            reason="Call buyer",
        ),
        _row(
            row_id="B__P2",
            customer="B",
            product_code="P2",
            product_name="Slight",
            last_year=100,
            last_month=95,
            current=60,
            final=95,
            budget=100,
            price=10,
        ),
        _row(
            row_id="C__P3",
            customer="C",
            product_code="P3",
            product_name="Growth",
            last_year=100,
            last_month=100,
            current=80,
            final=120,
            budget=110,
            price=10,
        ),
        _row(
            row_id="D__P4",
            customer="D",
            product_code="P4",
            product_name="No History",
            last_year=0,
            last_month=0,
            current=3,
            final=6,
            budget=5,
            price=10,
        ),
    ]

    monitor_rows = build_product_monitor_rows(rows)
    by_product = {row.product_code: row for row in monitor_rows}

    assert by_product["P1"].status == "高風險"
    assert by_product["P1"].diff_quantity == -11
    assert by_product["P1"].note == "Call buyer"
    assert by_product["P2"].status == "輕微下滑"
    assert by_product["P3"].status == "正常/成長"
    assert by_product["P4"].status == "無去年同期"


def test_data_health_summary_reports_source_coverage_and_row_anomalies():
    rows = [
        _row(
            row_id="A__P1",
            customer="A",
            product_code="P1",
            product_name="Missing Budget",
            last_year=20,
            last_month=10,
            current=2,
            final=15,
            budget=0,
            price=10,
        ),
        replace(
            _row(
                row_id="B__P2",
                customer="B",
                product_code="P2",
                product_name="Zero Price",
                last_year=0,
                last_month=5,
                current=1,
                final=5,
                budget=5,
                price=0,
            ),
            estimated_amount=0,
        ),
    ]
    sales_data = pd.DataFrame(
        {
            "order_date": pd.to_datetime(["2026-04-01", "2026-04-30"]),
        }
    )

    health = build_data_health_summary(
        sales_data,
        ForecastSummary(year=2026, month=5, rows=rows, total=150),
        budget_months=[(2026, 1), (2026, 5)],
    )

    assert health.order_count == 2
    assert health.order_start == date(2026, 4, 1)
    assert health.order_end == date(2026, 4, 30)
    assert health.budget_month_count == 2
    assert health.missing_budget_row_count == 1
    assert health.zero_price_row_count == 1
    assert health.no_last_year_row_count == 1
