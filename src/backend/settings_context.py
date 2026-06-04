from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from src.backend.data_validator import DataIssue, validate_budget_coverage, validate_health
from src.backend.database import MORDatabase
from src.backend.forecast_config import ForecastConfig
from src.backend.forecast_workbench_context import build as build_forecast_page_context


@dataclass(frozen=True)
class SettingsPageContext:
    items: list[dict]
    health: Any | None
    data_issues: list[DataIssue]
    year: int | str
    month: int | str
    error_message: str | None = None


def build_settings_page_context(
    forecast_config: ForecastConfig,
    db: MORDatabase,
    args: Mapping[str, object],
) -> SettingsPageContext:
    forecast_context = build_forecast_page_context(forecast_config, db, args)
    items = forecast_context.items
    budget_codes = _budget_product_codes(db, forecast_context.target.year)
    sales_codes = {item["product_code"] for item in items}
    data_issues = validate_health(forecast_context.health)
    data_issues += validate_budget_coverage(sales_codes, budget_codes)

    return SettingsPageContext(
        items=items,
        health=forecast_context.health,
        data_issues=data_issues,
        year=forecast_context.target.year,
        month=forecast_context.target.month,
    )


def build_settings_error_context(
    exc: Exception,
    *,
    fallback_year: object = "",
    fallback_month: object = "",
) -> SettingsPageContext:
    return SettingsPageContext(
        items=[],
        health=None,
        data_issues=[],
        year=fallback_year or "",
        month=fallback_month or "",
        error_message=f"載入系統設定失敗：{exc}",
    )


def _budget_product_codes(db: MORDatabase, year: int) -> set[str]:
    with db.get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT product_code FROM budget_targets WHERE year = ?",
            (year,),
        ).fetchall()
    return {row["product_code"] for row in rows}
