from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from typing import Mapping

import pandas as pd

from src.backend.daily_sales_importer import DailyActualAggregate
from src.backend.data_loader import default_target_from_db
from src.backend.amount_calculation import amount_for_quantity, forecast_amount_total
from src.backend.forecast_config import ForecastConfig
from src.backend.forecast_engine import ForecastOptions, build_forecast
from src.backend.forecast_models import ForecastRow, ForecastSummary, ForecastTarget
from src.backend.forecast_workbench_inputs import (
    BudgetTarget,
    ForecastRowMonthInput,
    ForecastWorkbenchInputs,
    load_forecast_workbench_inputs,
)
from src.backend.history_service import enrich_rows_with_history
from src.backend.dashboard_metrics import DashboardMetrics
from src.backend.data_health_summary import DataHealthSummary, build_data_health_summary
from src.backend.forecast_workbench_inputs import build_items_from_sales_data
from src.backend.product_monitor_month_context import (
    build_product_monitor_month_context,
)
from src.backend.product_monitor_rows import ProductMonitorRow
from src.backend.web.form_parser import parse_target_period


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
    monitor_context = build_product_monitor_month_context(
        db=db,
        rows=summary.rows,
        daily_actuals=inputs.daily_actuals,
        company_budgets=inputs.company_budgets,
        target=target,
        today=context_today,
        amount_for_quantity=amount_for_quantity,
    )
    return ForecastPageContext(
        target=target,
        sales_data=inputs.data,
        summary=summary,
        dashboard=monitor_context.dashboard,
        monitor_rows=monitor_context.monitor_rows,
        health=build_data_health_summary(inputs.data, summary, inputs.available_budget_months),
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


def _filter_visible_rows(
    summary: ForecastSummary,
    inputs: ForecastWorkbenchInputs,
) -> ForecastSummary:
    """Remove rows whose product_code is marked is_visible=False."""
    visible = [
        row for row in summary.rows
        if inputs.visible_product(row.product_code)
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
            excluded_item_ids=inputs.forecast_excluded_product_ids,
        ),
        forecast_config,
    )
    summary = _filter_visible_rows(summary, inputs)
    summary = replace(summary, rows=enrich_rows_with_history(summary.rows, db, target.year, target.month))
    summary = _patch_target_month_actuals(summary, inputs.daily_actuals, target)
    summary = apply_workbench_row_inputs(summary, inputs)
    return replace(summary, total=forecast_amount_total(summary.rows))


def apply_workbench_row_inputs(
    summary: ForecastSummary,
    inputs: ForecastWorkbenchInputs,
) -> ForecastSummary:
    rows = [
        _apply_workbench_row_input(
            row,
            inputs.row_month_input(row.row_id, row.product_code),
        )
        for row in summary.rows
    ]
    return replace(summary, rows=rows)


def _apply_workbench_row_input(
    row: ForecastRow,
    row_input: ForecastRowMonthInput,
) -> ForecastRow:
    manual_adjustment = (
        row_input.manual_adjustment
        if row_input.manual_adjustment is not None
        else row.manual_adjustment
    )
    row = row.with_adjustment(manual_adjustment, row.excluded)
    row = replace(
        row,
        adjustment_reason=row_input.adjustment_reason or row.adjustment_reason,
        budget_quantity=row_input.current_budget.target_quantity,
        budget_amount=row_input.current_budget.target_amount,
        base_budget_quantity=row_input.current_budget.base_target_quantity,
        price_quantity=row_input.price_quantity,
        item_status=row_input.item_status,
        budget_monthly=row_input.budget_monthly,
        budget_monthly_amount=row_input.budget_monthly_amount,
    )
    return replace(
        row,
        estimated_amount=0.0 if row.excluded else amount_for_quantity(row.final_forecast, row),
    )


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

