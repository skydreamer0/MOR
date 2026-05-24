from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Mapping

from src.backend.daily_sales_importer import DailyActualAggregate, fetch_daily_actuals_by_row_id
from src.backend.data_loader import default_target_from_db, load_sales_detail_from_db
from src.backend.forecast_config import ForecastConfig
from src.backend.forecast_engine import ForecastOptions, apply_user_adjustments, build_forecast
from src.backend.forecast_models import ForecastSummary, ForecastTarget
from src.backend.history_service import enrich_rows_with_history
from src.backend.operational_views import (
    _ForecastInputs,
    _apply_reasons_and_budgets,
    _patch_latest_order_dates,
    build_dashboard_metrics,
    build_data_health_summary,
    build_items_from_sales_data,
    build_product_monitor_rows,
    ForecastPageContext,
    forecast_amount_total,
    list_budget_months,
    load_adjustments,
    load_budget_year,
    load_budget_year_amounts,
    load_budgets,
    load_item_configs,
)
from src.backend.projection_engine import ProjectionResult, batch_project_eom
from src.backend.web.form_parser import parse_target_period
from src.backend.workday_calendar import ensure_calendar_year


def build(
    forecast_config: ForecastConfig,
    db,
    target_source: Mapping[str, object],
    *,
    today: date | None = None,
) -> ForecastPageContext:
    target = _resolve_target(db, target_source)
    inputs = _load_inputs(db, target)
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


def _load_inputs(db, target: ForecastTarget) -> _ForecastInputs:
    data = load_sales_detail_from_db(db)
    item_configs = load_item_configs(db)
    excluded_item_ids = frozenset(pid for pid, cfg in item_configs.items() if cfg["is_excluded"])
    manual_adjustments, adjustment_reasons = load_adjustments(db, target.year, target.month)
    return _ForecastInputs(
        data=data,
        item_configs=item_configs,
        excluded_item_ids=excluded_item_ids,
        manual_adjustments=manual_adjustments,
        adjustment_reasons=adjustment_reasons,
        budget_targets=load_budgets(db, target.year, target.month),
        budget_year_map=load_budget_year(db, target.year),
        budget_year_amount_map=load_budget_year_amounts(db, target.year),
        budget_months=list_budget_months(db),
        daily_actuals=fetch_daily_actuals_by_row_id(db, target.year, target.month),
    )


def _build_summary(
    inputs: _ForecastInputs,
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
    summary = _apply_reasons_and_budgets(
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
