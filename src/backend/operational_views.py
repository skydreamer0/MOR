from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Iterable, Mapping

import pandas as pd

from src.backend.analytics import AnalyticsSlice
from src.backend.amount_calculation import (
    amount_for_quantity,
    forecast_amount_total as _forecast_amount_total,
    is_amount_included,
    last_year_amount_total as _last_year_amount_total,
    latest_price_quantity,
    recalculate_forecast_amounts as _recalculate_forecast_amounts,
)
from src.backend.daily_sales_importer import DailyActualAggregate
from src.backend.data_loader import normalize_product_code
from src.backend.forecast_config import ForecastConfig
from src.backend.forecast_models import ForecastRow, ForecastSummary, ForecastTarget
from src.backend.forecast_workbench_inputs import BudgetTarget
from src.backend.product_monitor_rows import (
    ProductMonitorRow,
    _cycle_status_info,
    _fetch_monthly_history,
    _three_axis_status,
    _to_monitor_row as _build_product_monitor_row,
    build_product_monitor_rows as _build_product_monitor_rows,
    is_high_risk_drop,
)
from src.backend.projection_engine import ProjectionResult
from src.backend.row_identity import make_row_id


@dataclass(frozen=True)
class DashboardMetrics:
    target_quantity: float
    target_amount: float
    actual_quantity: float
    actual_amount: float
    forecast_quantity: float
    forecast_amount: float
    achievement_rate: float
    amount_achievement_rate: float
    quantity_gap: float
    amount_gap: float
    high_risk_product_count: int
    high_risk_customer_count: int


@dataclass(frozen=True)
class CustomerRiskItem:
    customer: str
    gap_amount: float
    gap_quantity: float
    item_count: int


@dataclass(frozen=True)
class DataHealthSummary:
    order_count: int
    order_start: date | None
    order_end: date | None
    budget_month_count: int
    budget_months: list[tuple[int, int]]
    missing_budget_row_count: int
    zero_price_row_count: int
    no_last_year_row_count: int


@dataclass(frozen=True)
class MonthlyReviewRow:
    customer: str
    product_code: str
    product_name: str
    actual_quantity: float
    actual_amount: float
    forecast_quantity: float
    forecast_amount: float
    forecast_gap_quantity: float
    forecast_gap_amount: float
    budget_quantity: float
    budget_amount: float
    budget_gap_quantity: float
    budget_gap_amount: float
    last_year_quantity: float
    last_year_amount: float
    year_gap_quantity: float
    year_gap_amount: float


@dataclass(frozen=True)
class MonthlyReviewTotals:
    actual_quantity: float
    actual_amount: float
    forecast_quantity: float
    forecast_amount: float
    forecast_gap_quantity: float
    forecast_gap_amount: float
    budget_quantity: float
    budget_amount: float
    budget_gap_quantity: float
    budget_gap_amount: float
    last_year_quantity: float
    last_year_amount: float
    year_gap_quantity: float
    year_gap_amount: float


@dataclass(frozen=True)
class MonthlyReviewReport:
    totals: MonthlyReviewTotals
    rows: list[MonthlyReviewRow]


def build_forecast_page_context(
    data_base_path: Path,
    forecast_config: ForecastConfig,
    db,
    target_source: Mapping[str, object],
    *,
    today: "date | None" = None,
) -> ForecastPageContext:
    from src.backend.forecast_workbench_context import build

    return build(forecast_config, db, target_source, today=today)


def __getattr__(name: str):
    if name == "ForecastPageContext":
        from src.backend.forecast_workbench_context import ForecastPageContext

        return ForecastPageContext
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def build_monthly_review_report(context: ForecastPageContext) -> MonthlyReviewReport:
    month_index = context.target.month - 1
    rows = [
        _to_monthly_review_row(row, month_index)
        for row in context.summary.rows
        if not row.excluded
    ]
    rows.sort(key=lambda row: (abs(row.forecast_gap_amount), abs(row.budget_gap_amount)), reverse=True)
    return MonthlyReviewReport(
        totals=MonthlyReviewTotals(
            actual_quantity=sum(row.actual_quantity for row in rows),
            actual_amount=sum(row.actual_amount for row in rows),
            forecast_quantity=sum(row.forecast_quantity for row in rows),
            forecast_amount=sum(row.forecast_amount for row in rows),
            forecast_gap_quantity=sum(row.forecast_gap_quantity for row in rows),
            forecast_gap_amount=sum(row.forecast_gap_amount for row in rows),
            budget_quantity=sum(row.budget_quantity for row in rows),
            budget_amount=sum(row.budget_amount for row in rows),
            budget_gap_quantity=sum(row.budget_gap_quantity for row in rows),
            budget_gap_amount=sum(row.budget_gap_amount for row in rows),
            last_year_quantity=sum(row.last_year_quantity for row in rows),
            last_year_amount=sum(row.last_year_amount for row in rows),
            year_gap_quantity=sum(row.year_gap_quantity for row in rows),
            year_gap_amount=sum(row.year_gap_amount for row in rows),
        ),
        rows=rows,
    )


def build_dashboard_metrics(
    rows: Iterable[ForecastRow],
    company_budgets: Iterable[BudgetTarget] | None = None,
    projections: Mapping[str, ProjectionResult] | None = None,
    daily_actuals: Mapping[str, DailyActualAggregate] | None = None,
) -> DashboardMetrics:
    included_rows = [row for row in rows if not row.excluded]
    budgeted_rows = [row for row in included_rows if row.budget_quantity > 0]
    target_quantity, target_amount = _target_totals(budgeted_rows, company_budgets)
    actuals = daily_actuals or {}
    actual_quantity = sum(row.this_year_same_month_qty for row in budgeted_rows)
    # Use taxed_amount from daily actuals when available — more accurate than qty × price
    actual_amount = sum(
        float(actuals[row.row_id].taxed_amount) if row.row_id in actuals
        else _dashboard_amount(row.this_year_same_month_qty, row)
        for row in budgeted_rows
    )

    # Use cycle-based projection for forecast if available; fall back to final_forecast
    projs = projections or {}
    def _eom_qty(row: ForecastRow) -> float:
        return projs[row.row_id].estimated_eom_qty if row.row_id in projs else row.final_forecast

    forecast_quantity = sum(_eom_qty(row) for row in budgeted_rows)
    forecast_amount = sum(_dashboard_amount(_eom_qty(row), row) for row in budgeted_rows)

    high_risk_rows = [row for row in included_rows if is_high_risk_drop(row)]

    return DashboardMetrics(
        target_quantity=target_quantity,
        target_amount=target_amount,
        actual_quantity=actual_quantity,
        actual_amount=actual_amount,
        forecast_quantity=forecast_quantity,
        forecast_amount=forecast_amount,
        achievement_rate=(forecast_quantity / target_quantity * 100) if target_quantity > 0 else 0.0,
        amount_achievement_rate=(forecast_amount / target_amount * 100) if target_amount > 0 else 0.0,
        quantity_gap=forecast_quantity - target_quantity,
        amount_gap=forecast_amount - target_amount,
        high_risk_product_count=len({row.product_code for row in high_risk_rows}),
        high_risk_customer_count=len({row.customer for row in high_risk_rows}),
    )


def forecast_amount_total(rows: Iterable[ForecastRow]) -> float:
    return _forecast_amount_total(rows)


def last_year_amount_total(rows: Iterable[ForecastRow]) -> float:
    return _last_year_amount_total(rows)


def recalculate_forecast_amounts(rows: Iterable[ForecastRow]) -> list[ForecastRow]:
    return _recalculate_forecast_amounts(rows)


def _is_amount_included(row: ForecastRow) -> bool:
    return is_amount_included(row)


def _target_totals(
    budgeted_rows: Iterable[ForecastRow],
    company_budgets: Iterable[BudgetTarget] | None,
) -> tuple[float, float]:
    if company_budgets is not None:
        budgets = list(company_budgets)
        return (
            sum(budget.target_quantity for budget in budgets),
            sum(budget.target_amount for budget in budgets),
        )

    rows = list(budgeted_rows)
    return (
        sum(row.budget_quantity for row in rows),
        sum(
            row.budget_amount if row.budget_amount > 0 else _dashboard_amount(row.budget_quantity, row)
            for row in rows
        ),
    )


def _dashboard_amount(quantity: float, row: ForecastRow) -> float:
    return amount_for_quantity(quantity, row)


def _amount_from_latest_order_price(quantity: float, row: ForecastRow) -> float:
    return amount_for_quantity(quantity, row)


def _latest_price_quantity(row: ForecastRow) -> float:
    return latest_price_quantity(row)


def _to_monthly_review_row(row: ForecastRow, month_index: int) -> MonthlyReviewRow:
    actual_quantity = row.this_year_same_month_qty
    actual_amount = row.ty_monthly_amount[month_index] if 0 <= month_index < len(row.ty_monthly_amount) else 0.0
    forecast_quantity = row.final_forecast
    forecast_amount = _dashboard_amount(forecast_quantity, row)
    budget_amount = row.budget_amount if row.budget_amount > 0 else _dashboard_amount(row.budget_quantity, row)
    last_year_quantity = row.last_year_same_month_qty
    last_year_amount = row.ly_monthly_amount[month_index] if 0 <= month_index < len(row.ly_monthly_amount) else 0.0
    return MonthlyReviewRow(
        customer=row.customer,
        product_code=row.product_code,
        product_name=row.product_name,
        actual_quantity=actual_quantity,
        actual_amount=actual_amount,
        forecast_quantity=forecast_quantity,
        forecast_amount=forecast_amount,
        forecast_gap_quantity=actual_quantity - forecast_quantity,
        forecast_gap_amount=actual_amount - forecast_amount,
        budget_quantity=row.budget_quantity,
        budget_amount=budget_amount,
        budget_gap_quantity=actual_quantity - row.budget_quantity,
        budget_gap_amount=actual_amount - budget_amount,
        last_year_quantity=last_year_quantity,
        last_year_amount=last_year_amount,
        year_gap_quantity=actual_quantity - last_year_quantity,
        year_gap_amount=actual_amount - last_year_amount,
    )


def build_product_monitor_rows(
    rows: Iterable[ForecastRow],
    daily_actuals: Mapping[str, DailyActualAggregate] | None = None,
    db=None,
    today: date | None = None,
    projections: Mapping[str, ProjectionResult] | None = None,
    target_month: int = 0,
) -> list[ProductMonitorRow]:
    return _build_product_monitor_rows(
        rows,
        daily_actuals=daily_actuals,
        db=db,
        today=today,
        projections=projections,
        target_month=target_month,
        amount_for_quantity=_dashboard_amount,
    )


def build_data_health_summary(
    sales_data: pd.DataFrame,
    summary: ForecastSummary,
    budget_months: Iterable[tuple[int, int]],
) -> DataHealthSummary:
    order_dates = pd.to_datetime(sales_data.get("order_date", pd.Series(dtype="datetime64[ns]")), errors="coerce").dropna()
    normalized_budget_months = sorted(set(budget_months))
    rows = [row for row in summary.rows if not row.excluded]
    return DataHealthSummary(
        order_count=len(sales_data),
        order_start=order_dates.min().date() if not order_dates.empty else None,
        order_end=order_dates.max().date() if not order_dates.empty else None,
        budget_month_count=len(normalized_budget_months),
        budget_months=normalized_budget_months,
        missing_budget_row_count=sum(1 for row in rows if row.budget_quantity <= 0),
        zero_price_row_count=sum(1 for row in rows if row.latest_price <= 0),
        no_last_year_row_count=sum(1 for row in rows if row.last_year_same_month_qty <= 0),
    )


def build_items_from_sales_data(data: pd.DataFrame, db) -> list[dict]:
    from src.backend.forecast_workbench_inputs import build_items_from_sales_data as _impl

    return _impl(data, db)


def load_item_configs(db) -> dict[str, dict]:
    from src.backend.forecast_workbench_inputs import load_item_configs as _impl

    return _impl(db)


def load_adjustments(db, year: int, month: int) -> tuple[dict[str, float], dict[str, str]]:
    from src.backend.forecast_workbench_inputs import load_adjustments as _impl

    return _impl(db, year, month)


def load_exclusions(db) -> set[str]:
    with db.get_connection() as conn:
        rows = conn.execute("SELECT product_code FROM item_configs WHERE is_excluded = 1").fetchall()
    excluded = set()
    for row in rows:
        product_code = row["product_code"]
        excluded.add(product_code)
        excluded.add(normalize_product_code(product_code))
    return excluded


def load_budgets(db, year: int, month: int) -> dict[str, BudgetTarget]:
    from src.backend.forecast_workbench_inputs import load_budgets as _impl

    return _impl(db, year, month)


def load_budget_year(db, year: int) -> dict[str, list[float]]:
    from src.backend.forecast_workbench_inputs import load_budget_year as _impl

    return _impl(db, year)


def load_budget_year_amounts(db, year: int) -> dict[str, list[float]]:
    from src.backend.forecast_workbench_inputs import load_budget_year_amounts as _impl

    return _impl(db, year)


def update_item_configs(db, items: list[dict]) -> None:
    """Upsert item config rows.  Each dict must have product_code plus any
    subset of: is_excluded, is_budgeted, is_visible, price_quantity, item_status.
    """
    with db.get_connection() as conn:
        for item in items:
            pid = normalize_product_code(item["product_code"])
            is_excluded   = int(bool(item.get("is_excluded", False)))
            is_budgeted   = int(bool(item.get("is_budgeted", True)))
            is_visible    = int(bool(item.get("is_visible", True)))
            price_quantity = int(item.get("price_quantity", 0))
            item_status   = item.get("item_status", "active")
            if item_status not in {"active", "discontinued"}:
                item_status = "active"
            conn.execute("""
                INSERT OR IGNORE INTO item_configs
                (product_code, is_excluded, is_budgeted, is_visible,
                 price_quantity, item_status, status_label, custom_category)
                VALUES (?, 0, 1, 1, 0, 'active', NULL, NULL)
            """, (pid,))
            conn.execute("""
                UPDATE item_configs
                SET is_excluded = ?, is_budgeted = ?, is_visible = ?,
                    price_quantity = ?, item_status = ?
                WHERE product_code = ?
            """, (is_excluded, is_budgeted, is_visible, price_quantity, item_status, pid))
        conn.commit()


def list_budget_months(db) -> list[tuple[int, int]]:
    from src.backend.forecast_workbench_inputs import list_budget_months as _impl

    return _impl(db)


def apply_reasons_and_budgets(
    summary: ForecastSummary,
    adjustment_reasons: dict[str, str],
    budget_targets: dict[str, BudgetTarget],
    item_configs: dict[str, dict] | None = None,
    budget_year_map: dict[str, list[float]] | None = None,
    budget_year_amount_map: dict[str, list[float]] | None = None,
) -> ForecastSummary:
    item_configs           = item_configs or {}
    budget_year_map        = budget_year_map or {}
    budget_year_amount_map = budget_year_amount_map or {}
    rows = [
        _apply_reason_and_budget(
            row, adjustment_reasons, budget_targets,
            item_configs, budget_year_map, budget_year_amount_map,
        )
        for row in summary.rows
    ]
    return replace(summary, rows=rows)


def _apply_reason_and_budget(
    row: ForecastRow,
    adjustment_reasons: dict[str, str],
    budget_targets: dict[str, BudgetTarget],
    item_configs: dict[str, dict],
    budget_year_map: dict[str, list[float]],
    budget_year_amount_map: dict[str, list[float]],
) -> ForecastRow:
    budget = budget_targets.get(row.row_id, BudgetTarget(0.0, 0.0))
    item_config = item_configs.get(row.product_code, {})
    is_budgeted = item_config.get("is_budgeted", True)
    if not is_budgeted:
        budget = BudgetTarget(0.0, 0.0)
    budget_monthly        = budget_year_map.get(row.row_id, [0.0] * 12)        if is_budgeted else [0.0] * 12
    budget_monthly_amount = budget_year_amount_map.get(row.row_id, [0.0] * 12) if is_budgeted else [0.0] * 12
    row = replace(
        row,
        adjustment_reason=adjustment_reasons.get(row.row_id, row.adjustment_reason),
        budget_quantity=budget.target_quantity,
        budget_amount=budget.target_amount,
        base_budget_quantity=budget.base_target_quantity,
        price_quantity=float(item_config.get("price_quantity") or 0),
        item_status=str(item_config.get("item_status") or "active"),
        budget_monthly=budget_monthly,
        budget_monthly_amount=budget_monthly_amount,
    )
    return replace(row, estimated_amount=0.0 if row.excluded else _dashboard_amount(row.final_forecast, row))


def _normalize_item_status(item_status: object, legacy_status_label: object = "") -> str:
    if str(item_status or "").strip() == "discontinued":
        return "discontinued"
    if str(legacy_status_label or "").strip() == "停用":
        return "discontinued"
    return "active"


def _to_monitor_row(
    row: ForecastRow,
    actual: DailyActualAggregate | None = None,
    workday_set: frozenset[date] | None = None,
    today: date | None = None,
    projection: ProjectionResult | None = None,
    target_month: int = 0,
) -> ProductMonitorRow:
    return _build_product_monitor_row(
        row,
        actual,
        workday_set,
        today,
        projection,
        target_month,
        amount_for_quantity=_dashboard_amount,
    )


def build_status_distribution(monitor_rows: list[ProductMonitorRow]) -> dict[str, int]:
    dist = {"high": 0, "caution": 0, "ok": 0, "no_history": 0}
    for row in monitor_rows:
        if row.status_key in dist:
            dist[row.status_key] += 1
    return dist


def build_customer_risk_ranking(
    monitor_rows: list[ProductMonitorRow],
    top_n: int = 5,
) -> list[CustomerRiskItem]:
    customer_gaps: dict[str, dict] = {}
    for row in monitor_rows:
        if row.status_key not in ("high", "caution"):
            continue
        if row.customer not in customer_gaps:
            customer_gaps[row.customer] = {"gap_amount": 0.0, "gap_quantity": 0.0, "item_count": 0}
        agg = customer_gaps[row.customer]
        agg["gap_amount"] += row.amount_impact
        agg["gap_quantity"] += row.diff_quantity
        agg["item_count"] += 1
    ranking = [
        CustomerRiskItem(customer=name, **data)
        for name, data in customer_gaps.items()
    ]
    ranking.sort(key=lambda x: x.gap_amount)
    return ranking[:top_n]


def aggregate_to_analytics(
    rows: list[ForecastRow],
    entity_type: str,
    target: ForecastTarget,
) -> list[dict]:
    """
    Aggregate ForecastRow monthly arrays by entity_type and return
    a list of AnalyticsSlice.to_dict() ready for JSON embedding.

    entity_type: "total" | "customer" | "product"
    Sorted by ytd_ty descending (highest revenue first).
    """
    groups: dict[str, list[ForecastRow]] = {}
    labels: dict[str, str] = {}

    for row in rows:
        if row.excluded:
            continue
        if entity_type == "total":
            key, label = "total", "全公司"
        elif entity_type == "customer":
            key, label = row.customer, row.customer
        else:  # product
            key, label = row.product_code, row.product_name

        groups.setdefault(key, []).append(row)
        labels[key] = label

    result: list[dict] = []
    for entity_id, entity_rows in groups.items():
        ly  = [sum(r.ly_monthly[i]     for r in entity_rows) for i in range(12)]
        ty  = [sum(r.ty_monthly[i]     for r in entity_rows) for i in range(12)]
        bud = [sum(r.budget_monthly[i] for r in entity_rows) for i in range(12)]

        # Amount arrays (qty × price per transaction, pre-computed in ForecastRow)
        ly_amt  = [sum(r.ly_monthly_amount[i]     for r in entity_rows) for i in range(12)]
        ty_amt  = [sum(r.ty_monthly_amount[i]     for r in entity_rows) for i in range(12)]
        # Budget amounts use the original target_amount from budget_targets — not qty × current price
        bud_amt = [sum(r.budget_monthly_amount[i] for r in entity_rows) for i in range(12)]

        # Forecast: only target_month carries a value
        fcst = [0.0] * 12
        fcst[target.month - 1] = sum(r.final_forecast for r in entity_rows)
        fcst_amt = sum(r.estimated_amount for r in entity_rows)

        slc = AnalyticsSlice(
            entity_id=entity_id,
            entity_label=labels[entity_id],
            entity_type=entity_type,
            target_year=target.year,
            target_month=target.month,
            ly_monthly=ly,
            ty_monthly=ty,
            budget_monthly=bud,
            forecast_monthly=fcst,
            ly_monthly_amount=ly_amt,
            ty_monthly_amount=ty_amt,
            budget_monthly_amount=bud_amt,
            forecast_amount=fcst_amt,
        )
        result.append(slc.to_dict())

    result.sort(key=lambda x: x["ytd_ty"], reverse=True)
    return result
