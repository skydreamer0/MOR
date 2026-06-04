import pandas as pd

from src.backend.analytics import (
    AnalyticsSlice,
    build_all_slices,
    build_customer_risk_ranking,
    build_slice_from_df,
    build_status_distribution,
)
from src.backend.forecast_models import ForecastRow
from src.backend.product_monitor_rows import build_product_monitor_rows


def _make_slice(**kwargs) -> AnalyticsSlice:
    defaults = dict(
        entity_id="total",
        entity_label="全公司",
        entity_type="total",
        target_year=2026,
        target_month=4,
        ly_monthly=[0.0] * 12,
        ty_monthly=[0.0] * 12,
        budget_monthly=[0.0] * 12,
    )
    defaults.update(kwargs)
    return AnalyticsSlice(**defaults)


def test_ytd_sums_up_to_last_actual_month():
    ty = [10.0, 20.0, 30.0] + [0.0] * 9
    s = _make_slice(ty_monthly=ty, target_month=4)
    # last_actual_month = 3 (March, index 2), ytd = 10+20+30
    assert s.ytd_ty == 60.0


def test_ytd_budget_rate():
    s = _make_slice(
        ty_monthly=[100.0] + [0.0] * 11,
        budget_monthly=[200.0] + [0.0] * 11,
        target_month=2,
    )
    assert s.ytd_budget_rate == 50.0


def test_trend_direction_up():
    # target_month=7: recent=avg(ty[3:6]), prev=avg(ty[0:3])
    ty = [10.0, 10.0, 10.0, 50.0, 50.0, 50.0] + [0.0] * 6
    s = _make_slice(ty_monthly=ty, target_month=7)
    assert s.trend_direction == "up"


def test_build_slice_from_df_basic():
    sales_df = pd.DataFrame({
        "年": [2026],
        "月": [3],
        "客戶簡稱": ["A"],
        "商品號": ["P1"],
        "銷+贈S量": [10.0],
    })
    s = build_slice_from_df(
        sales_df=sales_df,
        budget_rows=[],
        target_year=2026,
        target_month=4,
        entity_type="row",
        entity_id="A__P1",
        entity_label="A / P1",
    )
    assert s.ty_monthly[2] == 10.0  # March = index 2


def test_build_all_slices_customer_type():
    sales_df = pd.DataFrame({
        "年": [2026, 2026],
        "月": [3, 3],
        "客戶簡稱": ["客戶A", "客戶B"],
        "商品號": ["P1", "P2"],
        "銷+贈S量": [10.0, 20.0],
    })
    slices = build_all_slices(sales_df, pd.DataFrame(), 2026, 4, "customer")
    entity_ids = {s.entity_id for s in slices}
    assert "客戶A" in entity_ids
    assert "客戶B" in entity_ids
    assert len(slices) == 2


def _forecast_row(
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
) -> ForecastRow:
    return ForecastRow(
        row_id=row_id,
        customer=customer,
        product_code=product_code,
        product_name=product_name,
        latest_order_date=None,
        cycle_days=30,
        next_order_date=None,
        auto_in_month=True,
        last_year_same_month_qty=last_year,
        this_year_same_month_qty=current,
        latest_price=price,
        system_forecast=final,
        manual_adjustment=None,
        final_forecast=final,
        estimated_amount=final * price,
        forecast_basis="data_driven",
        budget_quantity=budget,
        budget_amount=budget * price,
        last_month_actual=last_month,
        last_month_budget=budget,
    )


def test_status_distribution_counts_monitor_statuses():
    monitor_rows = build_product_monitor_rows(
        [
            _forecast_row("A__P1", "A", "P1", "High", 100, 80, 20, 80, 100, 10),
            _forecast_row("B__P2", "B", "P2", "Caution", 100, 95, 60, 95, 100, 10),
            _forecast_row("C__P3", "C", "P3", "OK", 100, 100, 100, 120, 100, 10),
            _forecast_row("D__P4", "D", "P4", "No History", 0, 0, 2, 4, 0, 10),
        ],
        amount_for_quantity=lambda qty, row: qty * row.latest_price,
    )

    dist = build_status_distribution(monitor_rows)

    assert dist == {"high": 1, "caution": 1, "ok": 1, "no_history": 1}
    assert sum(dist.values()) == len(monitor_rows)


def test_customer_risk_ranking_aggregates_high_and_slight_rows_by_amount_gap():
    monitor_rows = build_product_monitor_rows(
        [
            _forecast_row("A__P1", "Customer A", "P1", "High Risk", 100, 80, 20, 80, 100, 10),
            _forecast_row("A__P2", "Customer A", "P2", "Slight", 100, 95, 60, 95, 100, 20),
            _forecast_row("B__P3", "Customer B", "P3", "High Risk", 200, 150, 60, 150, 200, 30),
            _forecast_row("C__P4", "Customer C", "P4", "Growth", 100, 100, 100, 120, 100, 100),
        ],
        amount_for_quantity=lambda qty, row: qty * row.latest_price,
    )

    ranking = build_customer_risk_ranking(monitor_rows, top_n=2)

    assert [item.customer for item in ranking] == ["Customer B", "Customer A"]
    assert [item.gap_amount for item in ranking] == [-1500, -300]
    assert [item.gap_quantity for item in ranking] == [-50, -25]
    assert [item.item_count for item in ranking] == [1, 2]
