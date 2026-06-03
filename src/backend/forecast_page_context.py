from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Sequence

from src.backend.amount_calculation import forecast_amount_total, last_year_amount_total
from src.backend.forecast_models import ForecastRow, ForecastSummary


@dataclass(frozen=True)
class ForecastPageRenderContext:
    year: int | str
    month: int | str
    rows: list[ForecastRow]
    discontinued_rows: list[ForecastRow]
    discontinued_last_year_total: float
    total: float
    unrendered_total: float
    forecast_signature: str
    row_count: int
    shown_count: int
    customers: list[str]
    risk_levels: dict[str, str]


def build_forecast_page_render_context(
    summary: ForecastSummary | None,
    *,
    visible_row_limit: int,
    fallback_year: object = "",
    fallback_month: object = "",
) -> ForecastPageRenderContext:
    if summary is None:
        return ForecastPageRenderContext(
            year=fallback_year or "",
            month=fallback_month or "",
            rows=[],
            discontinued_rows=[],
            discontinued_last_year_total=0.0,
            total=0.0,
            unrendered_total=0.0,
            forecast_signature="",
            row_count=0,
            shown_count=0,
            customers=[],
            risk_levels={},
        )

    rows = summary.rows
    sorted_rows = sorted(
        rows,
        key=lambda row: (0 if forecast_row_risk(row) == "high" else 1, row.customer, row.product_code),
    )
    active_rows = [row for row in sorted_rows if row.item_status != "discontinued"]
    discontinued_rows = [row for row in sorted_rows if row.item_status == "discontinued"]
    visible_rows = active_rows[:visible_row_limit]
    rendered_rows = visible_rows + discontinued_rows
    visible_total = forecast_amount_total(visible_rows)

    return ForecastPageRenderContext(
        year=summary.year,
        month=summary.month,
        rows=visible_rows,
        discontinued_rows=discontinued_rows,
        discontinued_last_year_total=last_year_amount_total(discontinued_rows),
        total=summary.total,
        unrendered_total=summary.total - visible_total,
        forecast_signature=forecast_signature(summary),
        row_count=len(rows),
        shown_count=len(rendered_rows),
        customers=sorted({row.customer for row in visible_rows}),
        risk_levels=risk_levels(rendered_rows),
    )


def forecast_row_risk(row: ForecastRow) -> str:
    if row.last_year_same_month_qty > 0 and row.final_forecast < row.last_year_same_month_qty * 0.9:
        return "high"
    return "normal"


def risk_levels(rows: Sequence[ForecastRow]) -> dict[str, str]:
    return {row.row_id: forecast_row_risk(row) for row in rows}


def validate_forecast_signature(summary: ForecastSummary, submitted_signature: object) -> None:
    if not submitted_signature:
        return
    if str(submitted_signature) != forecast_signature(summary):
        raise ValueError("Forecast review changed. Reload the page before exporting.")


def forecast_signature(summary: ForecastSummary) -> str:
    lines = [f"{summary.year}-{summary.month:02d}"]
    for row in summary.rows:
        lines.append(
            "|".join(
                [
                    row.row_id,
                    f"{row.system_forecast:.8f}",
                    f"{row.latest_price:.8f}",
                    f"{row.estimated_amount:.8f}",
                    row.forecast_basis,
                ]
            )
        )
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()
