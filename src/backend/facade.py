"""Compatibility facade — preserves the old sales_forecast.py public API."""

from __future__ import annotations

from typing import Iterable

import pandas as pd

from src.backend.data_loader import default_target_from_data, load_sales_detail, prepare_sales_data
from src.backend.exporter import export_forecast
from src.backend.engine import ForecastOptions, ForecastTarget, apply_user_adjustments, build_forecast
from src.backend.models import ForecastRow, ForecastSummary
from src.web.form_parser import parse_excluded_ids, parse_manual_quantities


def build_forecast_rows(data: pd.DataFrame, year: int, month: int, include_all: bool = False) -> list[dict]:
    summary = build_forecast(data, ForecastTarget(year, month), ForecastOptions(include_all=include_all))
    return [row.to_dict() for row in summary.rows]


def summarize_rows(
    rows: Iterable[dict],
    manual_quantities: dict[str, float | None],
    excluded_ids: set[str],
) -> tuple[float, list[dict]]:
    typed_rows = [_row_from_dict(row) for row in rows]
    summary = ForecastSummary(year=0, month=0, rows=typed_rows, total=sum(row.estimated_amount for row in typed_rows))
    adjusted = apply_user_adjustments(summary, manual_quantities, excluded_ids)
    return adjusted.total, [row.to_dict() for row in adjusted.rows]


def export_forecast_excel(rows: list[dict], total: float, year: int, month: int):
    summary = ForecastSummary(year=year, month=month, rows=[_row_from_dict(row) for row in rows], total=total)
    return export_forecast(summary)


def _prepare_data(data: pd.DataFrame) -> pd.DataFrame:
    return prepare_sales_data(data)


def _row_from_dict(row: dict) -> ForecastRow:
    return ForecastRow(
        row_id=row["row_id"],
        customer=row["customer"],
        product_code=row["product_code"],
        product_name=row["product_name"],
        latest_order_date=row["latest_order_date"],
        cycle_days=row["cycle_days"],
        next_order_date=row["next_order_date"],
        auto_in_month=row["auto_in_month"],
        last_year_same_month_qty=row["last_year_same_month_qty"],
        this_year_same_month_qty=row["this_year_same_month_qty"],
        latest_price=row["latest_price"],
        forecast_quantity=row["forecast_quantity"],
        manual_quantity=row.get("manual_quantity"),
        effective_quantity=row["effective_quantity"],
        estimated_amount=row["estimated_amount"],
        forecast_basis=row["forecast_basis"],
        excluded=row.get("excluded", False),
    )
