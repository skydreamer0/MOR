from __future__ import annotations

from types import SimpleNamespace

from src.backend import settings_context as ctx_module
from src.backend.data_validator import DataIssue
from src.backend.settings_context import build_settings_error_context, build_settings_page_context


def test_build_settings_page_context_assembles_items_health_and_budget_coverage(monkeypatch):
    db = object()
    forecast_context = SimpleNamespace(
        items=[{"product_code": "P1"}],
        health=SimpleNamespace(zero_price_row_count=2),
        target=SimpleNamespace(year=2026, month=5),
    )

    monkeypatch.setattr(ctx_module, "build_forecast_page_context", lambda config, db_arg, args: forecast_context)
    monkeypatch.setattr(ctx_module, "_budget_product_codes", lambda db_arg, year: {"P1", "P2"})

    context = build_settings_page_context(SimpleNamespace(), db, {"year": "2026", "month": "5"})

    assert context.items == [{"product_code": "P1"}]
    assert context.health is forecast_context.health
    assert context.year == 2026
    assert context.month == 5
    assert context.error_message is None
    assert context.data_issues == [
        DataIssue("warning", "有 2 筆單價為 0，金額估算可能不準確"),
        DataIssue("warning", "有 1 個預算品項在業績明細中無對應紀錄，GAP 計算可能不完整"),
    ]


def test_build_settings_error_context_preserves_fallback_shape():
    context = build_settings_error_context(
        ValueError("bad target"),
        fallback_year="bad-year",
        fallback_month="bad-month",
    )

    assert context.items == []
    assert context.health is None
    assert context.data_issues == []
    assert context.year == "bad-year"
    assert context.month == "bad-month"
    assert context.error_message == "載入系統設定失敗：bad target"
