from __future__ import annotations

from types import SimpleNamespace

from src.backend import monthly_review_context as ctx_module
from src.backend.monthly_review_context import build_monthly_review_context


def test_build_monthly_review_context_assembles_all_review_regions(monkeypatch):
    calls: list[str] = []
    db = object()
    summary = SimpleNamespace(name="summary")
    actions = SimpleNamespace(name="actions")
    customers = SimpleNamespace(name="customers")
    products = SimpleNamespace(name="products")
    bias = SimpleNamespace(name="bias")
    trend = SimpleNamespace(points=[object()])
    chart = SimpleNamespace(name="chart")

    monkeypatch.setattr(ctx_module, "build_monthly_review", lambda db_arg, y, m: calls.append(f"summary:{y}/{m}") or summary)
    monkeypatch.setattr(ctx_module, "build_action_lists", lambda db_arg, y, m: calls.append("actions") or actions)
    monkeypatch.setattr(ctx_module, "build_customer_summary", lambda db_arg, y, m: calls.append("customers") or customers)
    monkeypatch.setattr(ctx_module, "build_product_summary", lambda db_arg, y, m: calls.append("products") or products)
    monkeypatch.setattr(ctx_module, "build_forecast_bias", lambda db_arg, y, m: calls.append("bias") or bias)
    monkeypatch.setattr(ctx_module, "build_trend", lambda db_arg, y, m: calls.append("trend") or trend)
    monkeypatch.setattr(ctx_module, "build_trend_chart", lambda trend_arg: calls.append("chart") or chart)

    context = build_monthly_review_context(db, 2026, 5)

    assert calls == ["summary:2026/5", "actions", "customers", "products", "bias", "trend", "chart"]
    assert context.summary is summary
    assert context.action_lists is actions
    assert context.customer_summary is customers
    assert context.product_summary is products
    assert context.forecast_bias is bias
    assert context.trend is trend
    assert context.trend_chart is chart


def test_build_monthly_review_context_can_skip_html_chart(monkeypatch):
    monkeypatch.setattr(ctx_module, "build_monthly_review", lambda db, y, m: SimpleNamespace())
    monkeypatch.setattr(ctx_module, "build_action_lists", lambda db, y, m: SimpleNamespace())
    monkeypatch.setattr(ctx_module, "build_customer_summary", lambda db, y, m: SimpleNamespace())
    monkeypatch.setattr(ctx_module, "build_product_summary", lambda db, y, m: SimpleNamespace())
    monkeypatch.setattr(ctx_module, "build_forecast_bias", lambda db, y, m: SimpleNamespace())
    monkeypatch.setattr(ctx_module, "build_trend", lambda db, y, m: SimpleNamespace(points=[]))

    chart_calls = []
    monkeypatch.setattr(ctx_module, "build_trend_chart", lambda trend: chart_calls.append(trend))

    context = build_monthly_review_context(object(), 2026, 5, include_chart=False)

    assert context.trend_chart is None
    assert chart_calls == []
