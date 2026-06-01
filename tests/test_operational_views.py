from dataclasses import replace
from datetime import date

import pandas as pd
import pytest

from src.backend.daily_sales_importer import DailyActualAggregate
from src.backend.forecast_models import ForecastRow, ForecastSummary
from src.backend.row_identity import make_row_id
from src.backend.operational_views import (
    BudgetTarget,
    apply_reasons_and_budgets,
    _fetch_monthly_history,
    _patch_latest_order_dates,
    build_customer_risk_ranking,
    build_dashboard_metrics,
    build_data_health_summary,
    build_product_monitor_rows,
    build_status_distribution,
    load_adjustments,
    load_budget_year,
    load_budget_year_amounts,
    load_budgets,
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
    excluded: bool = False,
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
        excluded=excluded,
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
    assert metrics.actual_amount == 950
    assert metrics.forecast_quantity == 145
    assert metrics.forecast_amount == 2150
    assert metrics.quantity_gap == -25
    assert metrics.amount_gap == -550
    assert metrics.achievement_rate == 145 / 170 * 100
    assert metrics.high_risk_product_count == 1
    assert metrics.high_risk_customer_count == 1


def test_dashboard_metrics_use_company_budget_totals_above_workbench_rules():
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
            row_id="B__P2",
            customer="B",
            product_code="P2",
            product_name="Excluded Budget",
            last_year=20,
            last_month=10,
            current=5,
            final=10,
            budget=30,
            price=20,
            budget_amount=600,
            excluded=True,
        ),
    ]
    company_budgets = [
        BudgetTarget(target_quantity=120, target_amount=1500),
        BudgetTarget(target_quantity=30, target_amount=600),
        BudgetTarget(target_quantity=7, target_amount=250),
    ]

    metrics = build_dashboard_metrics(rows, company_budgets)

    assert metrics.target_quantity == 157
    assert metrics.target_amount == 2350
    assert metrics.forecast_quantity == 80
    assert metrics.forecast_amount == 800
    assert metrics.amount_gap == -1550


def test_budget_context_uses_latest_order_price_with_budget_quantity_unit():
    row = _row(
        row_id="A__P1",
        customer="A",
        product_code="P1",
        product_name="Latest Price",
        last_year=0,
        last_month=0,
        current=20,
        final=250,
        budget=0,
        price=3200,
    )

    summary = apply_reasons_and_budgets(
        ForecastSummary(year=2026, month=5, rows=[row], total=row.estimated_amount),
        adjustment_reasons={},
        budget_targets={
            row.row_id: BudgetTarget(
                target_quantity=280,
                target_amount=2800,
                base_target_quantity=1,
            )
        },
    )
    updated = summary.rows[0]
    metrics = build_dashboard_metrics(summary.rows)

    assert updated.latest_price == 3200
    assert updated.estimated_amount == 250 / 280 * 3200
    assert metrics.target_amount == 2800
    assert metrics.forecast_amount == 250 / 280 * 3200


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
            product_name="Caution",        # formerly "Slight", now "注意"
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
            budget=0,   # no budget → truly no comparison data → no_history
            price=10,
        ),
    ]

    monitor_rows = build_product_monitor_rows(rows)
    by_product = {row.product_code: row for row in monitor_rows}

    assert by_product["P1"].status == "高風險"
    assert by_product["P1"].status_key == "high"
    assert by_product["P1"].diff_quantity == -11
    assert by_product["P1"].note == "Call buyer"
    assert by_product["P2"].status == "注意"
    assert by_product["P2"].status_key == "caution"
    assert by_product["P3"].status == "正常/成長"
    assert by_product["P4"].status == "無去年同期"
    assert by_product["P4"].status_key == "no_history"


def test_status_distribution_counts_monitor_rows_by_status():
    monitor_rows = build_product_monitor_rows(
        [
            _row(
                row_id="A__P1",
                customer="A",
                product_code="P1",
                product_name="High Risk",
                last_year=100,
                last_month=80,
                current=20,
                final=80,
                budget=100,
                price=10,
            ),
            _row(
                row_id="B__P2",
                customer="B",
                product_code="P2",
                product_name="Caution",
                last_year=100,
                last_month=95,
                current=70,
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
                current=100,
                final=110,
                budget=100,
                price=10,
            ),
            _row(
                row_id="D__P4",
                customer="D",
                product_code="P4",
                product_name="No History",
                last_year=0,
                last_month=0,
                current=2,
                final=4,
                budget=0,   # no budget → no_history
                price=10,
            ),
        ]
    )

    dist = build_status_distribution(monitor_rows)

    assert dist == {"high": 1, "caution": 1, "ok": 1, "no_history": 1}
    assert sum(dist.values()) == len(monitor_rows)


def test_customer_risk_ranking_aggregates_high_and_slight_rows_by_amount_gap():
    monitor_rows = build_product_monitor_rows(
        [
            _row(
                row_id="A__P1",
                customer="Customer A",
                product_code="P1",
                product_name="High Risk",
                last_year=100,
                last_month=80,
                current=20,
                final=80,
                budget=100,
                price=10,
            ),
            _row(
                row_id="A__P2",
                customer="Customer A",
                product_code="P2",
                product_name="Slight",
                last_year=100,
                last_month=95,
                current=60,
                final=95,
                budget=100,
                price=20,
            ),
            _row(
                row_id="B__P3",
                customer="Customer B",
                product_code="P3",
                product_name="High Risk",
                last_year=200,
                last_month=150,
                current=60,
                final=150,
                budget=200,
                price=30,
            ),
            _row(
                row_id="C__P4",
                customer="Customer C",
                product_code="P4",
                product_name="Growth",
                last_year=100,
                last_month=100,
                current=100,
                final=120,
                budget=100,
                price=100,
            ),
        ]
    )

    ranking = build_customer_risk_ranking(monitor_rows, top_n=2)

    assert [item.customer for item in ranking] == ["Customer B", "Customer A"]
    assert [item.gap_amount for item in ranking] == [-1500, -300]
    assert [item.gap_quantity for item in ranking] == [-50, -25]
    assert [item.item_count for item in ranking] == [1, 2]


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


def test_product_monitor_current_quantity_prefers_daily_actual_lookup():
    row = _row(
        row_id="Hospital A__P1",
        customer="Hospital A",
        product_code="P1",
        product_name="Product One",
        last_year=10,
        last_month=0,
        current=3,
        final=8,
        budget=10,
        price=100,
    )
    actuals = {
        "Hospital A__P1": DailyActualAggregate(
            actual_quantity=12,
            taxed_amount=1200,
            latest_sales_date="2026-05-08",
        )
    }

    monitor_rows = build_product_monitor_rows([row], daily_actuals=actuals)

    assert monitor_rows[0].current_quantity == 12


def test_monitor_row_pack_factor_only_applies_when_actual_is_present():
    """包裝量只在有每日業績匯入時套用；無匯入資料時歷史數量直接使用（已是展示單位）。"""
    base = _row(
        row_id="A__P1",
        customer="A",
        product_code="P1",
        product_name="Packed",
        last_year=100,
        last_month=50,
        current=80,
        final=90,
        budget=100,
        price=10,
    )
    from dataclasses import replace as dreplace
    row_with_pack = dreplace(base, price_quantity=6.0)

    from src.backend.operational_views import _to_monitor_row
    from src.backend.daily_sales_importer import DailyActualAggregate

    # 沒有每日業績資料時：this_year_same_month_qty 直接用（不乘 pack_factor）
    mr_no_actual = _to_monitor_row(row_with_pack)
    assert mr_no_actual.current_quantity == 80  # 不乘

    # 有每日業績資料時：actual_quantity × pack_factor
    actual = DailyActualAggregate(actual_quantity=10, taxed_amount=1000, latest_sales_date=None)
    mr_with_actual = _to_monitor_row(row_with_pack, actual=actual)
    assert mr_with_actual.current_quantity == 10 * 6  # 乘 pack_factor

    # 其他欄位不受影響
    assert mr_with_actual.last_year_quantity == 100
    assert mr_with_actual.forecast_quantity == 90
    assert mr_with_actual.yoy_growth_rate == pytest.approx(90 / 100)


# ---------------------------------------------------------------------------
# Phase 3: 3-axis status logic
# ---------------------------------------------------------------------------

from src.backend.operational_views import _three_axis_status, _cycle_status_info


def test_three_axis_status_high_risk_from_yoy():
    status, key = _three_axis_status(
        yoy_rate=0.85, bud_rate=1.1, cycle_high=False, cycle_caution=False,
        last_year_qty=100, budget_qty=100,
    )
    assert key == "high"
    assert status == "高風險"


def test_three_axis_status_high_risk_from_budget():
    status, key = _three_axis_status(
        yoy_rate=1.05, bud_rate=0.80, cycle_high=False, cycle_caution=False,
        last_year_qty=100, budget_qty=100,
    )
    assert key == "high"


def test_three_axis_status_high_risk_from_cycle():
    status, key = _three_axis_status(
        yoy_rate=1.05, bud_rate=1.05, cycle_high=True, cycle_caution=False,
        last_year_qty=100, budget_qty=100,
    )
    assert key == "high"


def test_three_axis_status_caution_from_yoy():
    status, key = _three_axis_status(
        yoy_rate=0.95, bud_rate=1.05, cycle_high=False, cycle_caution=False,
        last_year_qty=100, budget_qty=100,
    )
    assert key == "caution"
    assert status == "注意"


def test_three_axis_status_caution_from_cycle():
    status, key = _three_axis_status(
        yoy_rate=1.1, bud_rate=1.1, cycle_high=False, cycle_caution=True,
        last_year_qty=100, budget_qty=100,
    )
    assert key == "caution"


def test_three_axis_status_ok():
    status, key = _three_axis_status(
        yoy_rate=1.05, bud_rate=1.10, cycle_high=False, cycle_caution=False,
        last_year_qty=100, budget_qty=100,
    )
    assert key == "ok"
    assert status == "正常/成長"


def test_three_axis_status_no_history_when_no_comparison_data():
    status, key = _three_axis_status(
        yoy_rate=None, bud_rate=None, cycle_high=False, cycle_caution=False,
        last_year_qty=0, budget_qty=0,
    )
    assert key == "no_history"


def test_three_axis_status_with_budget_only_is_not_no_history():
    # Has budget data → should evaluate on budget axis, not fall into no_history
    status, key = _three_axis_status(
        yoy_rate=None, bud_rate=1.2, cycle_high=False, cycle_caution=False,
        last_year_qty=0, budget_qty=100,
    )
    assert key == "ok"


def test_cycle_status_delayed():
    cs, high, caution = _cycle_status_info(days_since=50, cycle_days=40)
    assert cs == "delayed"
    assert high is True
    assert caution is False


def test_cycle_status_approaching():
    cs, high, caution = _cycle_status_info(days_since=33, cycle_days=40)
    assert cs == "approaching"
    assert high is False
    assert caution is True


def test_cycle_status_ok():
    cs, high, caution = _cycle_status_info(days_since=20, cycle_days=40)
    assert cs == "ok"
    assert high is False
    assert caution is False


def test_cycle_status_no_cycle_when_none():
    cs, high, caution = _cycle_status_info(days_since=None, cycle_days=None)
    assert cs == "no_cycle"
    assert high is False


def test_monitor_row_cycle_delay_forces_high_risk():
    """A row with good YoY and budget but overdue cycle → 高風險."""
    row = _row(
        row_id="A__P1",
        customer="A",
        product_code="P1",
        product_name="Overdue",
        last_year=100,
        last_month=90,
        current=50,
        final=105,  # yoy 105% and budget 105% — both fine
        budget=100,
        price=10,
    )
    # Simulate 60 workdays since last order with avg cycle of 40 days → 60 > 40*1.2=48 → delayed
    from src.backend.forecast_models import replace as dreplace
    row = dreplace(row, cycle_days=40)

    # Build a workday_set that puts 60 days between order_date (2026-04-20) and today
    from datetime import date, timedelta
    today = date(2026, 6, 30)
    order_date = date(2026, 4, 20)
    # Mon–Fri workdays between 2026-04-21 and 2026-06-30
    workday_set = frozenset(
        order_date + timedelta(days=i)
        for i in range(1, (today - order_date).days + 1)
        if (order_date + timedelta(days=i)).weekday() < 5
    )

    from src.backend.operational_views import _to_monitor_row
    monitor_row = _to_monitor_row(row, workday_set=workday_set, today=today)

    assert monitor_row.cycle_status == "delayed"
    assert monitor_row.status_key == "high"
    assert monitor_row.days_since_last_shipment_workdays is not None
    assert monitor_row.days_since_last_shipment_workdays > 48


# ---------------------------------------------------------------------------
# build_forecast_page_context — DB-first (Phase 2)
# ---------------------------------------------------------------------------

def _make_db_with_sales():
    import tempfile
    from pathlib import Path
    from src.backend.database import MORDatabase

    tmp = tempfile.mkstemp(suffix=".db")[1]
    db = MORDatabase(Path(tmp))
    with db.get_connection() as conn:
        # Two months of historical data so forecast_engine can derive patterns
        for month, day, qty in [(3, 10, 20), (3, 25, 20), (4, 12, 18), (4, 28, 18)]:
            conn.execute(
                "INSERT INTO sales_records "
                "(order_date, customer_name, product_code, product_name, quantity, unit_price, amount) "
                "VALUES (?, 'A客戶', 'P1', '商品A', ?, 100, ?)",
                (f"2026-{month:02d}-{day:02d}", qty, qty * 100),
            )
        conn.commit()
    return db


def test_build_forecast_page_context_uses_db_not_excel(tmp_path):
    """build_forecast_page_context must serve data from DB without any Excel file present."""
    from src.backend.forecast_config import ForecastConfig
    from src.backend.operational_views import build_forecast_page_context

    db = _make_db_with_sales()
    config = ForecastConfig()

    # No Excel file exists in tmp_path — context must still build from DB
    ctx = build_forecast_page_context(tmp_path, config, db, {"year": "2026", "month": "5"})

    assert ctx.target.year == 2026
    assert ctx.target.month == 5
    # sales_data should contain the DB rows
    assert len(ctx.sales_data) > 0


def test_build_forecast_page_context_accepts_today_parameter(tmp_path):
    """build_forecast_page_context must thread an explicit today to the projection engine."""
    from src.backend.forecast_config import ForecastConfig
    from src.backend.operational_views import build_forecast_page_context

    db = _make_db_with_sales()
    config = ForecastConfig()
    specific_today = date(2026, 5, 15)
    ctx = build_forecast_page_context(tmp_path, config, db, {"year": "2026", "month": "5"}, today=specific_today)
    assert ctx.target.year == 2026
    assert ctx.target.month == 5


# ---------------------------------------------------------------------------
# _patch_latest_order_dates — current-month daily actuals update ForecastRow
# ---------------------------------------------------------------------------

def test_forecast_workbench_context_build_matches_legacy_context_contract():
    from src.backend.forecast_config import ForecastConfig
    from src.backend.forecast_workbench_context import build
    from src.backend.operational_views import build_forecast_page_context

    db = _make_db_with_sales()
    config = ForecastConfig()
    target_source = {"year": "2026", "month": "5"}

    workbench_context = build(config, db, target_source, today=date(2026, 5, 15))
    legacy_context = build_forecast_page_context(None, config, db, target_source)

    assert workbench_context.target == legacy_context.target
    assert len(workbench_context.summary.rows) == len(legacy_context.summary.rows)
    assert len(workbench_context.sales_data) == len(legacy_context.sales_data)
    assert workbench_context.dashboard.forecast_quantity >= 0
    assert workbench_context.monitor_rows
    assert workbench_context.health.order_count == legacy_context.health.order_count
    assert workbench_context.items


def _summary_with_rows(rows: list) -> ForecastSummary:
    return ForecastSummary(year=2026, month=5, rows=rows, total=0.0)


def test_patch_latest_order_dates_updates_when_actual_is_newer():
    row = _row(
        row_id="A__P1", customer="A", product_code="P1", product_name="X",
        last_year=100, last_month=80, current=20, final=80, budget=100, price=10,
    )
    # row.latest_order_date is 2026-04-20 (set in _row helper)
    actuals = {
        "A__P1": DailyActualAggregate(
            actual_quantity=30, taxed_amount=0, latest_sales_date="2026-05-08"
        )
    }
    patched = _patch_latest_order_dates(_summary_with_rows([row]), actuals)

    assert patched.rows[0].latest_order_date == date(2026, 5, 8)


def test_patch_latest_order_dates_keeps_original_when_actual_is_older():
    row = _row(
        row_id="A__P1", customer="A", product_code="P1", product_name="X",
        last_year=100, last_month=80, current=20, final=80, budget=100, price=10,
    )
    # row.latest_order_date = 2026-04-20; actual has an older date (shouldn't override)
    actuals = {
        "A__P1": DailyActualAggregate(
            actual_quantity=10, taxed_amount=0, latest_sales_date="2026-04-01"
        )
    }
    patched = _patch_latest_order_dates(_summary_with_rows([row]), actuals)

    assert patched.rows[0].latest_order_date == date(2026, 4, 20)


def test_patch_latest_order_dates_no_change_when_no_actual():
    row = _row(
        row_id="A__P1", customer="A", product_code="P1", product_name="X",
        last_year=100, last_month=80, current=20, final=80, budget=100, price=10,
    )
    patched = _patch_latest_order_dates(_summary_with_rows([row]), {})

    assert patched.rows[0].latest_order_date == date(2026, 4, 20)


def test_patch_latest_order_dates_uses_actual_when_row_date_is_none():
    row = _row(
        row_id="A__P1", customer="A", product_code="P1", product_name="X",
        last_year=100, last_month=80, current=20, final=80, budget=100, price=10,
    )
    row = replace(row, latest_order_date=None)
    actuals = {
        "A__P1": DailyActualAggregate(
            actual_quantity=15, taxed_amount=0, latest_sales_date="2026-05-02"
        )
    }
    patched = _patch_latest_order_dates(_summary_with_rows([row]), actuals)

    assert patched.rows[0].latest_order_date == date(2026, 5, 2)


def test_patch_latest_order_dates_skips_row_when_actual_sales_date_is_none():
    row = _row(
        row_id="A__P1", customer="A", product_code="P1", product_name="X",
        last_year=100, last_month=80, current=20, final=80, budget=100, price=10,
    )
    actuals = {
        "A__P1": DailyActualAggregate(
            actual_quantity=10, taxed_amount=0, latest_sales_date=None
        )
    }
    patched = _patch_latest_order_dates(_summary_with_rows([row]), actuals)

    assert patched.rows[0].latest_order_date == date(2026, 4, 20)


def test_operational_lookup_maps_use_canonical_row_identity_for_delimiter_collisions(tmp_path):
    from src.backend.database import MORDatabase

    db = MORDatabase(tmp_path / "mor_workbench.db")
    first = make_row_id("A__B", "C")
    second = make_row_id("A", "B__C")
    with db.get_connection() as conn:
        conn.execute(
            """
            INSERT INTO forecast_adjustments
            (year, month, customer_name, product_code, manual_quantity, adjustment_reason)
            VALUES (2026, 5, 'A__B', 'C', 5, 'first')
            """
        )
        conn.execute(
            """
            INSERT INTO forecast_adjustments
            (year, month, customer_name, product_code, manual_quantity, adjustment_reason)
            VALUES (2026, 5, 'A', 'B__C', 8, 'second')
            """
        )
        conn.execute(
            """
            INSERT INTO budget_targets
            (year, month, customer_name, product_code, target_quantity, target_amount, base_target_quantity)
            VALUES (2026, 5, 'A__B', 'C', 50, 500, 5)
            """
        )
        conn.execute(
            """
            INSERT INTO budget_targets
            (year, month, customer_name, product_code, target_quantity, target_amount, base_target_quantity)
            VALUES (2026, 5, 'A', 'B__C', 80, 800, 8)
            """
        )
        conn.commit()

    manual_adjustments, adjustment_reasons = load_adjustments(db, 2026, 5)
    budgets = load_budgets(db, 2026, 5)
    budget_year = load_budget_year(db, 2026)
    budget_year_amounts = load_budget_year_amounts(db, 2026)

    assert manual_adjustments[first] == 5
    assert manual_adjustments[second] == 8
    assert adjustment_reasons[first] == "first"
    assert adjustment_reasons[second] == "second"
    assert budgets[first].target_quantity == 50
    assert budgets[second].target_amount == 800
    assert budget_year[first][4] == 50
    assert budget_year[second][4] == 80
    assert budget_year_amounts[first][4] == 500
    assert budget_year_amounts[second][4] == 800


def test_monthly_history_uses_canonical_row_identity_for_delimiter_collisions(tmp_path):
    from src.backend.database import MORDatabase

    db = MORDatabase(tmp_path / "mor_workbench.db")
    first = make_row_id("A__B", "C")
    second = make_row_id("A", "B__C")
    with db.get_connection() as conn:
        for customer, product, qty, budget in [
            ("A__B", "C", 5, 50),
            ("A", "B__C", 8, 80),
        ]:
            conn.execute(
                """
                INSERT INTO sales_records
                (order_date, customer_name, product_code, product_name, quantity, unit_price, amount)
                VALUES ('2026-04-10', ?, ?, '', ?, 0, 0)
                """,
                (customer, product, qty),
            )
            conn.execute(
                """
                INSERT INTO budget_targets
                (year, month, customer_name, product_code, target_quantity)
                VALUES (2026, 4, ?, ?, ?)
                """,
                (customer, product, budget),
            )
        conn.commit()

    histories = _fetch_monthly_history(
        db,
        [("A__B", "C"), ("A", "B__C")],
        [(2026, 4)],
    )

    assert histories[first][0]["actual"] == 5
    assert histories[first][0]["budget"] == 50
    assert histories[second][0]["actual"] == 8
    assert histories[second][0]["budget"] == 80
