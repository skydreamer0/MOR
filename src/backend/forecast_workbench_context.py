from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from typing import Mapping

import pandas as pd

from src.backend.daily_sales_importer import DailyActualAggregate
from src.backend.data_loader import default_target_from_db
from src.backend.forecast_config import ForecastConfig
from src.backend.forecast_engine import ForecastOptions, apply_user_adjustments, build_forecast
from src.backend.forecast_models import ForecastRow, ForecastSummary, ForecastTarget
from src.backend.forecast_workbench_inputs import (
    ForecastWorkbenchInputs,
    load_forecast_workbench_inputs,
)
from src.backend.history_service import enrich_rows_with_history
from src.backend.operational_views import (
    apply_reasons_and_budgets,
    build_dashboard_metrics,
    build_data_health_summary,
    build_items_from_sales_data,
    build_product_monitor_rows,
    DashboardMetrics,
    DataHealthSummary,
    forecast_amount_total,
)
from src.backend.product_monitor_rows import ProductMonitorRow
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
        ),
        health=build_data_health_summary(inputs.data, summary, inputs.budget_months),
        items=build_items_from_sales_data(inputs.data, db),
    )


def _resolve_target(db, target_source: Mapping[str, object]) -> ForecastTarget:
    default_target = default_target_from_db(db)
    return parse_target_period(target_source, default_target)


def _patch_latest_order_dates(
    summary: ForecastSummary,
    daily_actuals: Mapping[str, DailyActualAggregate],
) -> ForecastSummary:
    """Update ForecastRow.latest_order_date using current-month daily actuals."""
    patched = []
    for row in summary.rows:
        actual = daily_actuals.get(row.row_id)
        if actual is not None and actual.latest_sales_date is not None:
            new_date = date.fromisoformat(str(actual.latest_sales_date)[:10])
            if row.latest_order_date is None or new_date > row.latest_order_date:
                row = replace(row, latest_order_date=new_date)
        patched.append(row)
    return replace(summary, rows=patched)


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
    visible_rows = [
        row for row in summary.rows
        if inputs.item_configs.get(row.product_code, {}).get("is_visible", True)
    ]
    summary = replace(
        summary,
        rows=visible_rows,
        total=sum(row.estimated_amount for row in visible_rows if not row.excluded),
    )
    summary = replace(summary, rows=enrich_rows_with_history(summary.rows, db, target.year, target.month))
    summary = _patch_latest_order_dates(summary, inputs.daily_actuals)
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


def _build_projections(
    db,
    summary: ForecastSummary,
    daily_actuals: Mapping[str, DailyActualAggregate],
    today: date,
    target: ForecastTarget,
) -> dict[str, ProjectionResult]:
    ensure_calendar_year(db, today.year)
    return batch_project_eom(db, summary.rows, daily_actuals, today, target.year, target.month)
