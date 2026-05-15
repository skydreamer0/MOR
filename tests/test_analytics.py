import pandas as pd

from src.backend.analytics import AnalyticsSlice, build_all_slices, build_slice_from_df


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
