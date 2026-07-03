from datetime import date

from src.backend.forecast_models import ForecastTarget


def test_product_monitor_month_context_reuses_projection_results(monkeypatch):
    from src.backend import product_monitor_month_context as module

    db = object()
    rows = []
    daily_actuals = {}
    company_budgets = []
    today = date(2026, 5, 10)
    target = ForecastTarget(2026, 5)
    projections = {"row": object()}
    dashboard = object()
    monitor_rows = [object()]
    calls = {}

    def fake_ensure_calendar_year(db_arg, year_arg):
        calls["calendar"] = (db_arg, year_arg)

    def fake_batch_project_eom(db_arg, rows_arg, actuals_arg, today_arg, year_arg, month_arg):
        calls["projection"] = (db_arg, rows_arg, actuals_arg, today_arg, year_arg, month_arg)
        return projections

    def fake_build_dashboard_metrics(rows_arg, budgets_arg, projections_arg, actuals_arg):
        calls["dashboard"] = (rows_arg, budgets_arg, projections_arg, actuals_arg)
        return dashboard

    def fake_build_product_monitor_rows(
        rows_arg,
        *,
        daily_actuals,
        db,
        today,
        projections,
        target_month,
        amount_for_quantity,
    ):
        calls["monitor"] = (
            rows_arg,
            daily_actuals,
            db,
            today,
            projections,
            target_month,
            amount_for_quantity,
        )
        return monitor_rows

    monkeypatch.setattr(module, "ensure_calendar_year", fake_ensure_calendar_year)
    monkeypatch.setattr(module, "batch_project_eom", fake_batch_project_eom)
    monkeypatch.setattr(module, "build_dashboard_metrics", fake_build_dashboard_metrics)
    monkeypatch.setattr(module, "build_product_monitor_rows", fake_build_product_monitor_rows)

    amount_for_quantity = lambda quantity, row: quantity
    context = module.build_product_monitor_month_context(
        db=db,
        rows=rows,
        daily_actuals=daily_actuals,
        company_budgets=company_budgets,
        target=target,
        today=today,
        amount_for_quantity=amount_for_quantity,
    )

    assert context.projections is projections
    assert context.dashboard is dashboard
    assert context.monitor_rows == monitor_rows
    assert calls["calendar"] == (db, 2026)
    assert calls["projection"] == (db, rows, daily_actuals, today, 2026, 5)
    assert calls["dashboard"] == (rows, company_budgets, projections, daily_actuals)
    assert calls["monitor"] == (
        rows,
        daily_actuals,
        db,
        today,
        projections,
        5,
        amount_for_quantity,
    )
