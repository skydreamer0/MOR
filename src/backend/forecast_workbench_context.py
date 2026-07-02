from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from typing import Mapping

import pandas as pd

from src.backend.daily_sales_importer import DailyActualAggregate
from src.backend.data_loader import default_target_from_db
from src.backend.amount_calculation import amount_for_quantity, forecast_amount_total
from src.backend.forecast_config import ForecastConfig
from src.backend.forecast_engine import ForecastOptions, apply_user_adjustments, build_forecast
from src.backend.forecast_models import ForecastRow, ForecastSummary, ForecastTarget
from src.backend.forecast_workbench_inputs import (
    BudgetTarget,
    ForecastWorkbenchInputs,
    load_forecast_workbench_inputs,
)
from src.backend.history_service import enrich_rows_with_history
from src.backend.dashboard_metrics import DashboardMetrics, build_dashboard_metrics
from src.backend.data_health_summary import DataHealthSummary, build_data_health_summary
from src.backend.forecast_workbench_inputs import build_items_from_sales_data
from src.backend.product_monitor_rows import (
    ProductMonitorRow,
    build_product_monitor_rows,
)
from src.backend.projection_engine import ProjectionResult, batch_project_eom
from src.backend.web.form_parser import parse_target_period
from src.backend.workday_calendar import ensure_calendar_year


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


def build(
    forecast_config: ForecastConfig,
    db,
    target_source: Mapping[str, object],
    *,
    today: date | None = None,
) -> ForecastPageContext:
    target = _resolve_target(db, target_source)
    inputs = load_forecast_workbench_inputs(db, target)
    summary = _build_summary(inputs, db, target, forecast_config)
    context_today = today or date.today()
    projections = _build_projections(db, summary, inputs.daily_actuals, context_today, target)
    return ForecastPageContext(
        target=target,
        sales_data=inputs.data,
        summary=summary,
        dashboard=build_dashboard_metrics(
            summary.rows,
            inputs.budget_targets.values(),
            projections,
            inputs.daily_actuals,
        ),
        monitor_rows=build_product_monitor_rows(
            summary.rows,
            daily_actuals=inputs.daily_actuals,
            db=db,
            today=context_today,
            projections=projections,
            target_month=target.month,
            amount_for_quantity=amount_for_quantity,
        ),
        health=build_data_health_summary(inputs.data, summary, inputs.budget_months),
        items=build_items_from_sales_data(inputs.data, db),
    )


def _resolve_target(db, target_source: Mapping[str, object]) -> ForecastTarget:
    default_target = default_target_from_db(db)
    return parse_target_period(target_source, default_target)


def _patch_target_month_actuals(
    summary: ForecastSummary,
    daily_actuals: Mapping[str, DailyActualAggregate],
    target: ForecastTarget,
) -> ForecastSummary:
    """Patch target-month actual quantity/amount from imported daily actuals."""
    patched = []
    month_index = target.month - 1
    for row in summary.rows:
        actual = daily_actuals.get(row.row_id)
        if actual is None:
            patched.append(row)
            continue

        updates = {}
        if 0 <= month_index < 12:
            ty_monthly = list(row.ty_monthly)
            ty_monthly[month_index] = actual.actual_quantity
            ty_monthly_amount = list(row.ty_monthly_amount)
            ty_monthly_amount[month_index] = actual.taxed_amount
            updates.update(
                {
                    "this_year_same_month_qty": actual.actual_quantity,
                    "ty_monthly": ty_monthly,
                    "ty_monthly_amount": ty_monthly_amount,
                }
            )

        if actual.latest_sales_date is not None:
            new_date = date.fromisoformat(str(actual.latest_sales_date)[:10])
            if row.latest_order_date is None or new_date > row.latest_order_date:
                updates["latest_order_date"] = new_date

        if updates:
            row = replace(row, **updates)
        patched.append(row)
    return replace(summary, rows=patched)


def _filter_visible_rows(summary: ForecastSummary, item_configs: dict) -> ForecastSummary:
    """Remove rows whose product_code is marked is_visible=False in item_configs."""
    visible = [
        row for row in summary.rows
        if item_configs.get(row.product_code, {}).get("is_visible", True)
    ]
    return replace(
        summary,
        rows=visible,
        total=sum(row.estimated_amount for row in visible if not row.excluded),
    )


def _build_summary(
    inputs: ForecastWorkbenchInputs,
    db,
    target: ForecastTarget,
    forecast_config: ForecastConfig,
) -> ForecastSummary:
    summary = build_forecast(
        inputs.data,
        target,
        ForecastOptions(
            include_all=True,
            max_cycle_interval_days=forecast_config.max_cycle_interval_days,
            excluded_item_ids=inputs.excluded_item_ids,
        ),
        forecast_config,
    )
    summary = _filter_visible_rows(summary, inputs.item_configs)
    summary = replace(summary, rows=enrich_rows_with_history(summary.rows, db, target.year, target.month))
    summary = _patch_target_month_actuals(summary, inputs.daily_actuals, target)
    summary = apply_user_adjustments(summary, manual_adjustments=inputs.manual_adjustments, excluded_ids=set())
    summary = apply_reasons_and_budgets(
        summary,
        inputs.adjustment_reasons,
        inputs.budget_targets,
        inputs.item_configs,
        inputs.budget_year_map,
        inputs.budget_year_amount_map,
    )
    return replace(summary, total=forecast_amount_total(summary.rows))


def apply_reasons_and_budgets(
    summary: ForecastSummary,
    adjustment_reasons: dict[str, str],
    budget_targets: dict[str, BudgetTarget],
    item_configs: dict[str, dict] | None = None,
    budget_year_map: dict[str, list[float]] | None = None,
    budget_year_amount_map: dict[str, list[float]] | None = None,
) -> ForecastSummary:
    item_configs = item_configs or {}
    budget_year_map = budget_year_map or {}
    budget_year_amount_map = budget_year_amount_map or {}
    rows = [
        _apply_reason_and_budget(
            row,
            adjustment_reasons,
            budget_targets,
            item_configs,
            budget_year_map,
            budget_year_amount_map,
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
    budget_monthly = budget_year_map.get(row.row_id, [0.0] * 12) if is_budgeted else [0.0] * 12
    budget_monthly_amount = (
        budget_year_amount_map.get(row.row_id, [0.0] * 12)
        if is_budgeted
        else [0.0] * 12
    )
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
    return replace(row, estimated_amount=0.0 if row.excluded else amount_for_quantity(row.final_forecast, row))


def _build_projections(
    db,
    summary: ForecastSummary,
    daily_actuals: Mapping[str, DailyActualAggregate],
    today: date,
    target: ForecastTarget,
) -> dict[str, ProjectionResult]:
    ensure_calendar_year(db, today.year)
    return batch_project_eom(db, summary.rows, daily_actuals, today, target.year, target.month)
