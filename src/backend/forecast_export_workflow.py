from __future__ import annotations

from dataclasses import replace

from src.backend.amount_calculation import forecast_amount_total, recalculate_forecast_amounts
from src.backend.forecast_engine import apply_user_adjustments
from src.backend.forecast_models import ForecastSummary


def prepare_export_summary(
    summary: ForecastSummary,
    manual_adjustments: dict[str, float | None],
    adjustment_reasons: dict[str, str],
) -> ForecastSummary:
    summary = apply_user_adjustments(
        summary,
        manual_adjustments=manual_adjustments,
        excluded_ids=set(),
    )
    rows = [
        replace(row, adjustment_reason=adjustment_reasons.get(row.row_id, row.adjustment_reason))
        for row in summary.rows
    ]
    rows = recalculate_forecast_amounts(rows)
    return replace(summary, rows=rows, total=forecast_amount_total(rows))
