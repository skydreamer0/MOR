def test_workbench_context_owns_latest_order_date_patch_helper():
    from src.backend.forecast_workbench_context import _patch_latest_order_dates

    assert _patch_latest_order_dates.__module__ == "src.backend.forecast_workbench_context"


def test_workbench_context_owns_page_context_type():
    from src.backend.forecast_workbench_context import ForecastPageContext
    from src.backend.operational_views import ForecastPageContext as LegacyForecastPageContext

    assert ForecastPageContext.__module__ == "src.backend.forecast_workbench_context"
    assert LegacyForecastPageContext is ForecastPageContext
