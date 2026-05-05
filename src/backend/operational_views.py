from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Iterable, Mapping

import pandas as pd

from src.backend.data_loader import default_target_from_data, load_sales_detail, normalize_product_code
from src.backend.forecast_config import ForecastConfig
from src.backend.forecast_engine import ForecastOptions, apply_user_adjustments, build_forecast
from src.backend.forecast_models import ForecastRow, ForecastSummary, ForecastTarget
from src.backend.history_service import enrich_rows_with_history
from src.backend.web.form_parser import parse_target_period


DROP_RISK_THRESHOLD = 0.9


@dataclass(frozen=True)
class BudgetTarget:
    target_quantity: float
    target_amount: float
    base_target_quantity: float = 0.0


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
class ProductMonitorRow:
    customer: str
    product_code: str
    product_name: str
    last_year_quantity: float
    last_month_quantity: float
    current_quantity: float
    forecast_quantity: float
    diff_quantity: float
    drop_rate: float | None
    status: str
    status_key: str
    note: str
    latest_price: float = 0.0
    amount_impact: float = 0.0


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
class ForecastPageContext:
    target: ForecastTarget
    sales_data: pd.DataFrame
    summary: ForecastSummary
    dashboard: DashboardMetrics
    monitor_rows: list[ProductMonitorRow]
    health: DataHealthSummary
    items: list[dict]

    @property
    def rows(self) -> list[ForecastRow]:
        return self.summary.rows


def build_forecast_page_context(
    data_base_path: Path,
    forecast_config: ForecastConfig,
    db,
    target_source: Mapping[str, object],
) -> ForecastPageContext:
    data = load_sales_detail(data_base_path, forecast_config)
    default_target = default_target_from_data(data, forecast_config)
    target = parse_target_period(target_source, default_target)
    item_configs = load_item_configs(db)
    excluded_item_ids = {pid for pid, cfg in item_configs.items() if cfg["is_excluded"]}
    manual_adjustments, adjustment_reasons = load_adjustments(db, target.year, target.month)
    budget_targets = load_budgets(db, target.year, target.month)

    summary = build_forecast(
        data,
        target,
        ForecastOptions(
            include_all=True,
            max_cycle_interval_days=forecast_config.max_cycle_interval_days,
            excluded_item_ids=excluded_item_ids,
        ),
        forecast_config,
    )
    visible_rows = [
        row
        for row in summary.rows
        if item_configs.get(row.product_code, {}).get("is_visible", True)
    ]
    summary = replace(
        summary,
        rows=visible_rows,
        total=sum(row.estimated_amount for row in visible_rows if not row.excluded),
    )
    summary = replace(summary, rows=enrich_rows_with_history(summary.rows, db, target.year, target.month))
    summary = apply_user_adjustments(summary, manual_adjustments=manual_adjustments, excluded_ids=set())
    summary = _apply_reasons_and_budgets(summary, adjustment_reasons, budget_targets)
    summary = replace(summary, total=forecast_amount_total(summary.rows))

    budget_months = list_budget_months(db)
    return ForecastPageContext(
        target=target,
        sales_data=data,
        summary=summary,
        dashboard=build_dashboard_metrics(summary.rows, budget_targets.values()),
        monitor_rows=build_product_monitor_rows(summary.rows),
        health=build_data_health_summary(data, summary, budget_months),
        items=build_items_from_sales_data(data, db),
    )


def build_dashboard_metrics(
    rows: Iterable[ForecastRow],
    company_budgets: Iterable[BudgetTarget] | None = None,
) -> DashboardMetrics:
    included_rows = [row for row in rows if not row.excluded]
    budgeted_rows = [row for row in included_rows if row.budget_quantity > 0]
    target_quantity, target_amount = _target_totals(budgeted_rows, company_budgets)
    actual_quantity = sum(row.this_year_same_month_qty for row in budgeted_rows)
    actual_amount = sum(_dashboard_amount(row.this_year_same_month_qty, row) for row in budgeted_rows)
    forecast_quantity = sum(row.final_forecast for row in budgeted_rows)
    forecast_amount = sum(_dashboard_amount(row.final_forecast, row) for row in budgeted_rows)
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
    return sum(_dashboard_amount(row.final_forecast, row) for row in rows if _is_amount_included(row))


def _is_amount_included(row: ForecastRow) -> bool:
    return not row.excluded and row.budget_quantity > 0


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
            row.budget_amount if row.budget_amount > 0 else row.budget_quantity * row.latest_price
            for row in rows
        ),
    )


def _dashboard_amount(quantity: float, row: ForecastRow) -> float:
    return quantity * row.latest_price


def build_product_monitor_rows(rows: Iterable[ForecastRow]) -> list[ProductMonitorRow]:
    monitor_rows = [_to_monitor_row(row) for row in rows if not row.excluded]
    status_order = {"high": 0, "slight": 1, "ok": 2, "no_history": 3}
    return sorted(
        monitor_rows,
        key=lambda row: (status_order[row.status_key], row.diff_quantity, row.customer, row.product_code),
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


def is_high_risk_drop(row: ForecastRow) -> bool:
    return row.last_year_same_month_qty > 0 and row.final_forecast < row.last_year_same_month_qty * DROP_RISK_THRESHOLD


def build_items_from_sales_data(data: pd.DataFrame, db) -> list[dict]:
    unique_products = data[["商品號", "商品簡稱"]].drop_duplicates("商品號")
    item_configs = load_item_configs(db)
    items = []
    for _, row in unique_products.iterrows():
        product_code = normalize_product_code(row["商品號"])
        config = item_configs.get(
            product_code,
            {
                "is_excluded": False,
                "is_budgeted": True,
                "is_visible": True,
                "status_label": "",
            },
        )
        items.append(
            {
                "product_code": product_code,
                "product_name": row["商品簡稱"],
                **config,
            }
        )
    return items


def load_item_configs(db) -> dict[str, dict]:
    with db.get_connection() as conn:
        rows = conn.execute("SELECT * FROM item_configs").fetchall()
    configs = {
        row["product_code"]: {
            "is_excluded": bool(row["is_excluded"]),
            "is_budgeted": bool(row["is_budgeted"]),
            "is_visible": bool(row["is_visible"]),
            "status_label": row["status_label"],
        }
        for row in rows
    }
    for row in rows:
        normalized_code = normalize_product_code(row["product_code"])
        configs.setdefault(normalized_code, configs[row["product_code"]])
    return configs


def load_adjustments(db, year: int, month: int) -> tuple[dict[str, float], dict[str, str]]:
    manual_adjustments = {}
    adjustment_reasons = {}
    with db.get_connection() as conn:
        rows = conn.execute(
            """
            SELECT customer_name, product_code, manual_quantity, adjustment_reason
            FROM forecast_adjustments
            WHERE year = ? AND month = ?
            """,
            (year, month),
        ).fetchall()
    for row in rows:
        row_id = f"{row['customer_name']}__{row['product_code']}"
        if row["manual_quantity"] is not None:
            manual_adjustments[row_id] = row["manual_quantity"]
        if row["adjustment_reason"]:
            adjustment_reasons[row_id] = row["adjustment_reason"]
    return manual_adjustments, adjustment_reasons


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
    budgets = {}
    with db.get_connection() as conn:
        rows = conn.execute(
            """
            SELECT customer_name, product_code, target_quantity, target_amount, base_target_quantity
            FROM budget_targets
            WHERE year = ? AND month = ?
            """,
            (year, month),
        ).fetchall()
    for row in rows:
        row_id = f"{row['customer_name']}__{row['product_code']}"
        budgets[row_id] = BudgetTarget(
            target_quantity=float(row["target_quantity"] or 0),
            target_amount=float(row["target_amount"] or 0),
            base_target_quantity=float(row["base_target_quantity"] or 0),
        )
    return budgets


def list_budget_months(db) -> list[tuple[int, int]]:
    with db.get_connection() as conn:
        rows = conn.execute(
            """
            SELECT year, month
            FROM budget_targets
            GROUP BY year, month
            ORDER BY year, month
            """
        ).fetchall()
    return [(int(row["year"]), int(row["month"])) for row in rows]


def _apply_reasons_and_budgets(
    summary: ForecastSummary,
    adjustment_reasons: dict[str, str],
    budget_targets: dict[str, BudgetTarget],
) -> ForecastSummary:
    rows = [
        _apply_reason_and_budget(row, adjustment_reasons, budget_targets)
        for row in summary.rows
    ]
    return replace(summary, rows=rows)


def _apply_reason_and_budget(
    row: ForecastRow,
    adjustment_reasons: dict[str, str],
    budget_targets: dict[str, BudgetTarget],
) -> ForecastRow:
    budget = budget_targets.get(row.row_id, BudgetTarget(0.0, 0.0))
    return replace(
        row,
        adjustment_reason=adjustment_reasons.get(row.row_id, row.adjustment_reason),
        budget_quantity=budget.target_quantity,
        budget_amount=budget.target_amount,
        base_budget_quantity=budget.base_target_quantity,
    )


def _to_monitor_row(row: ForecastRow) -> ProductMonitorRow:
    diff_quantity = row.final_forecast - row.last_year_same_month_qty
    if row.last_year_same_month_qty <= 0:
        status = "無去年同期"
        status_key = "no_history"
        drop_rate = None
    else:
        drop_rate = diff_quantity / row.last_year_same_month_qty * 100
        if row.final_forecast < row.last_year_same_month_qty * DROP_RISK_THRESHOLD:
            status = "高風險"
            status_key = "high"
        elif row.final_forecast < row.last_year_same_month_qty:
            status = "輕微下滑"
            status_key = "slight"
        else:
            status = "正常/成長"
            status_key = "ok"

    amount_impact = diff_quantity * row.latest_price
    return ProductMonitorRow(
        customer=row.customer,
        product_code=row.product_code,
        product_name=row.product_name,
        last_year_quantity=row.last_year_same_month_qty,
        last_month_quantity=row.last_month_actual,
        current_quantity=row.this_year_same_month_qty,
        forecast_quantity=row.final_forecast,
        diff_quantity=diff_quantity,
        drop_rate=drop_rate,
        status=status,
        status_key=status_key,
        note=row.adjustment_reason or "",
        latest_price=row.latest_price,
        amount_impact=amount_impact,
    )


def build_status_distribution(monitor_rows: list[ProductMonitorRow]) -> dict[str, int]:
    dist = {"high": 0, "slight": 0, "ok": 0, "no_history": 0}
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
        if row.status_key not in ("high", "slight"):
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
