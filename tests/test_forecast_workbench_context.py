def test_workbench_context_owns_target_month_actual_patch_helper():
    from src.backend.forecast_workbench_context import _patch_target_month_actuals

    assert _patch_target_month_actuals.__module__ == "src.backend.forecast_workbench_context"


def test_workbench_context_owns_page_context_type():
    from src.backend.forecast_workbench_context import ForecastPageContext

    assert ForecastPageContext.__module__ == "src.backend.forecast_workbench_context"
