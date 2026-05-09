from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable, Mapping

import pandas as pd

from src.backend.analytics import AnalyticsSlice
from src.backend.daily_sales_importer import DailyActualAggregate, fetch_daily_actuals_by_row_id
from src.backend.data_loader import default_target_from_data, load_sales_detail, normalize_product_code
from src.backend.forecast_config import ForecastConfig
from src.backend.forecast_engine import ForecastOptions, apply_user_adjustments, build_forecast
from src.backend.forecast_models import ForecastRow, ForecastSummary, ForecastTarget
from src.backend.history_service import enrich_rows_with_history
from src.backend.web.form_parser import parse_target_period
from src.backend.projection_engine import ProjectionResult, batch_project_eom
from src.backend.workday_calendar import ensure_calendar_year, fetch_workday_set


DROP_RISK_THRESHOLD = 0.9

# Phase 3 thresholds for cycle-delay risk
_CYCLE_HIGH_MULTIPLIER = 1.2
_CYCLE_CAUTION_MULTIPLIER = 0.8


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
    # Phase 3: new monitoring axes
    latest_order_date: date | None = None
    days_since_last_shipment_workdays: int | None = None
    estimated_eom_qty: float = 0.0         # system forecast (Phase 4 refines this)
    yoy_growth_rate: float | None = None   # final_forecast / last_year (ratio)
    budget_achievement_rate: float | None = None  # final_forecast / budget (ratio)
    cycle_status: str = "no_cycle"         # "delayed" | "approaching" | "ok" | "no_cycle"
    cycle_days: int | None = None
    budget_quantity: float = 0.0
    # Phase 4: projection model details
    remaining_shipments: int = 0
    typical_qty_per_shipment: float = 0.0
    projection_confidence: str = "low"
    # Phase 5: three-axis amount comparison
    current_taxed_amount: float = 0.0   # 本月目前含稅淨額（daily actuals）
    estimated_eom_amount: float = 0.0   # 推估月底金額
    final_forecast_amount: float = 0.0  # 最終預估金額（= ForecastRow.estimated_amount）
    last_year_amount: float = 0.0       # 去年同期金額（0 = 無資料，顯示 -）
    budget_amount: float = 0.0          # 本月預算金額


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
    budget_targets         = load_budgets(db, target.year, target.month)
    budget_year_map        = load_budget_year(db, target.year)
    budget_year_amount_map = load_budget_year_amounts(db, target.year)

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
    summary = _apply_reasons_and_budgets(
        summary, adjustment_reasons, budget_targets,
        item_configs, budget_year_map, budget_year_amount_map,
    )
    summary = replace(summary, total=forecast_amount_total(summary.rows))

    budget_months = list_budget_months(db)
    daily_actuals = fetch_daily_actuals_by_row_id(db, target.year, target.month)
    today = date.today()
    ensure_calendar_year(db, today.year)
    projections = batch_project_eom(
        db, summary.rows, daily_actuals, today, target.year, target.month,
    )
    return ForecastPageContext(
        target=target,
        sales_data=data,
        summary=summary,
        dashboard=build_dashboard_metrics(summary.rows, budget_targets.values()),
        monitor_rows=build_product_monitor_rows(
            summary.rows,
            daily_actuals=daily_actuals,
            db=db,
            today=today,
            projections=projections,
            target_month=target.month,
        ),
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


def last_year_amount_total(rows: Iterable[ForecastRow]) -> float:
    return sum(_dashboard_amount(row.last_year_same_month_qty, row) for row in rows if not row.excluded)


def recalculate_forecast_amounts(rows: Iterable[ForecastRow]) -> list[ForecastRow]:
    return [
        replace(row, estimated_amount=0.0 if row.excluded else _dashboard_amount(row.final_forecast, row))
        for row in rows
    ]


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
            row.budget_amount if row.budget_amount > 0 else _dashboard_amount(row.budget_quantity, row)
            for row in rows
        ),
    )


def _dashboard_amount(quantity: float, row: ForecastRow) -> float:
    return _amount_from_latest_order_price(quantity, row)


def _amount_from_latest_order_price(quantity: float, row: ForecastRow) -> float:
    price_quantity = _latest_price_quantity(row)
    if price_quantity <= 0:
        return quantity * row.latest_price
    return quantity / price_quantity * row.latest_price


def _latest_price_quantity(row: ForecastRow) -> float:
    if row.price_quantity > 0:
        return row.price_quantity
    if row.budget_quantity > 0 and row.base_budget_quantity > 0:
        return row.budget_quantity / row.base_budget_quantity
    return 1.0


def build_product_monitor_rows(
    rows: Iterable[ForecastRow],
    daily_actuals: Mapping[str, DailyActualAggregate] | None = None,
    db=None,
    today: date | None = None,
    projections: Mapping[str, ProjectionResult] | None = None,
    target_month: int = 0,
) -> list[ProductMonitorRow]:
    today = today or date.today()
    actuals = daily_actuals or {}
    projs = projections or {}
    workday_set = fetch_workday_set(db, today - timedelta(days=400), today) if db is not None else None
    monitor_rows = [
        _to_monitor_row(row, actuals.get(row.row_id), workday_set, today, projs.get(row.row_id), target_month)
        for row in rows if not row.excluded
    ]
    status_order = {"high": 0, "caution": 1, "ok": 2, "no_history": 3}
    return sorted(
        monitor_rows,
        key=lambda r: (
            status_order.get(r.status_key, 3),
            r.budget_achievement_rate if r.budget_achievement_rate is not None else float("inf"),
            r.yoy_growth_rate if r.yoy_growth_rate is not None else float("inf"),
            -(r.days_since_last_shipment_workdays or 0),
        ),
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
                "price_quantity": 0.0,
                "item_status": "active",
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
            "price_quantity": float(row["price_quantity"] or 0),
            "item_status": _normalize_item_status(row["item_status"], row["status_label"]),
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


def load_budget_year(db, year: int) -> dict[str, list[float]]:
    """Return a 12-element monthly quantity array per row_id for the given year."""
    with db.get_connection() as conn:
        rows = conn.execute(
            """
            SELECT customer_name, product_code, month, target_quantity
            FROM budget_targets
            WHERE year = ?
            """,
            (year,),
        ).fetchall()
    result: dict[str, list[float]] = {}
    for row in rows:
        row_id = f"{row['customer_name']}__{row['product_code']}"
        if row_id not in result:
            result[row_id] = [0.0] * 12
        m = int(row["month"]) - 1          # 0-based index
        if 0 <= m < 12:
            result[row_id][m] = float(row["target_quantity"] or 0)
    return result


def load_budget_year_amounts(db, year: int) -> dict[str, list[float]]:
    """Return a 12-element monthly amount array per row_id for the given year.
    Uses target_amount as originally set in the budget — not quantity × current price.
    """
    with db.get_connection() as conn:
        rows = conn.execute(
            """
            SELECT customer_name, product_code, month, target_amount
            FROM budget_targets
            WHERE year = ?
            """,
            (year,),
        ).fetchall()
    result: dict[str, list[float]] = {}
    for row in rows:
        row_id = f"{row['customer_name']}__{row['product_code']}"
        if row_id not in result:
            result[row_id] = [0.0] * 12
        m = int(row["month"]) - 1
        if 0 <= m < 12:
            result[row_id][m] = float(row["target_amount"] or 0)
    return result


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


def _days_since_order(workday_set: frozenset[date], order_date: date, today: date) -> int:
    """Count workdays strictly after order_date up to and including today."""
    return sum(1 for d in workday_set if order_date < d <= today)


def _cycle_status_info(days_since: int | None, cycle_days: int | None) -> tuple[str, bool, bool]:
    """Return (cycle_status_key, is_high_risk, is_caution)."""
    if days_since is None or cycle_days is None or cycle_days <= 0:
        return "no_cycle", False, False
    if days_since > cycle_days * _CYCLE_HIGH_MULTIPLIER:
        return "delayed", True, False
    if days_since >= cycle_days * _CYCLE_CAUTION_MULTIPLIER:
        return "approaching", False, True
    return "ok", False, False


def _three_axis_status(
    yoy_rate: float | None,
    bud_rate: float | None,
    cycle_high: bool,
    cycle_caution: bool,
    last_year_qty: float,
    budget_qty: float,
) -> tuple[str, str]:
    """Derive (status_display, status_key) from the three monitoring axes."""
    has_comparison = last_year_qty > 0 or budget_qty > 0
    if not has_comparison and not cycle_high and not cycle_caution:
        return "無去年同期", "no_history"

    if (
        (yoy_rate is not None and yoy_rate < DROP_RISK_THRESHOLD)
        or (bud_rate is not None and bud_rate < DROP_RISK_THRESHOLD)
        or cycle_high
    ):
        return "高風險", "high"

    if (
        (yoy_rate is not None and yoy_rate < 1.0)
        or (bud_rate is not None and bud_rate < 1.0)
        or cycle_caution
    ):
        return "注意", "caution"

    return "正常/成長", "ok"


def _to_monitor_row(
    row: ForecastRow,
    actual: DailyActualAggregate | None = None,
    workday_set: frozenset[date] | None = None,
    today: date | None = None,
    projection: ProjectionResult | None = None,
    target_month: int = 0,
) -> ProductMonitorRow:
    today = today or date.today()
    # Prefer daily actuals (Phase 1) over historical this_year figure
    current_quantity = actual.actual_quantity if actual is not None else row.this_year_same_month_qty

    # Workday distance since last shipment
    # Prefer current-month daily-actual date over historical latest_order_date (Phase 4 fix)
    days_since: int | None = None
    if workday_set is not None:
        reference_date: date | None = None
        if actual is not None and actual.latest_sales_date is not None:
            raw = actual.latest_sales_date
            reference_date = date.fromisoformat(str(raw)[:10])
        elif row.latest_order_date:
            reference_date = row.latest_order_date
        if reference_date is not None:
            days_since = _days_since_order(workday_set, reference_date, today)

    # Rate computations (using final_forecast as the expected EOMonth quantity)
    yoy_rate = (row.final_forecast / row.last_year_same_month_qty) if row.last_year_same_month_qty > 0 else None
    bud_rate = (row.final_forecast / row.budget_quantity) if row.budget_quantity > 0 else None

    cycle_status_key, cycle_high, cycle_caution = _cycle_status_info(days_since, row.cycle_days)
    status, status_key = _three_axis_status(
        yoy_rate, bud_rate, cycle_high, cycle_caution,
        row.last_year_same_month_qty, row.budget_quantity,
    )

    diff_quantity = row.final_forecast - row.last_year_same_month_qty
    drop_rate = (diff_quantity / row.last_year_same_month_qty * 100) if row.last_year_same_month_qty > 0 else None
    amount_impact = _dashboard_amount(diff_quantity, row)

    # Phase 4: use projection model for estimated_eom_qty when available
    if projection is not None:
        estimated_eom = projection.estimated_eom_qty
        remaining_shipments = projection.remaining_shipments
        typical_qty = projection.typical_qty_per_shipment
        proj_confidence = projection.confidence
        projected_remaining_qty = projection.projected_remaining_qty
    else:
        estimated_eom = row.system_forecast
        remaining_shipments = 0
        typical_qty = 0.0
        proj_confidence = "low"
        projected_remaining_qty = 0.0

    # Phase 5: amount fields
    current_taxed_amount = float(actual.taxed_amount) if actual is not None else 0.0
    # Unit price for remaining projected shipments — prefer implied price from actuals
    if current_quantity > 0 and current_taxed_amount > 0:
        implied_unit_price = current_taxed_amount / current_quantity
    else:
        implied_unit_price = row.latest_price
    estimated_eom_amount = current_taxed_amount + projected_remaining_qty * implied_unit_price
    final_forecast_amount = float(row.estimated_amount)
    last_year_amount = (
        float(row.ly_monthly_amount[target_month - 1])
        if 1 <= target_month <= 12 else 0.0
    )
    budget_amount = float(row.budget_amount)

    return ProductMonitorRow(
        customer=row.customer,
        product_code=row.product_code,
        product_name=row.product_name,
        last_year_quantity=row.last_year_same_month_qty,
        last_month_quantity=row.last_month_actual,
        current_quantity=current_quantity,
        forecast_quantity=row.final_forecast,
        diff_quantity=diff_quantity,
        drop_rate=drop_rate,
        status=status,
        status_key=status_key,
        note=row.adjustment_reason or "",
        latest_price=row.latest_price,
        amount_impact=amount_impact,
        latest_order_date=row.latest_order_date,
        days_since_last_shipment_workdays=days_since,
        estimated_eom_qty=estimated_eom,
        yoy_growth_rate=yoy_rate,
        budget_achievement_rate=bud_rate,
        cycle_status=cycle_status_key,
        cycle_days=row.cycle_days,
        budget_quantity=row.budget_quantity,
        remaining_shipments=remaining_shipments,
        typical_qty_per_shipment=typical_qty,
        projection_confidence=proj_confidence,
        current_taxed_amount=current_taxed_amount,
        estimated_eom_amount=estimated_eom_amount,
        final_forecast_amount=final_forecast_amount,
        last_year_amount=last_year_amount,
        budget_amount=budget_amount,
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
