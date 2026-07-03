from __future__ import annotations

import ast
import inspect
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _imports_from(module_path: str, imported_from: str) -> set[str]:
    tree = ast.parse((PROJECT_ROOT / module_path).read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == imported_from:
            names.update(alias.name for alias in node.names)
    return names


def test_amount_helpers_are_imported_from_amount_calculation_not_operational_views():
    amount_helpers = {
        "amount_for_quantity",
        "forecast_amount_total",
        "last_year_amount_total",
        "recalculate_forecast_amounts",
    }
    phase_one_modules = [
        "src/backend/app.py",
        "src/backend/forecast_export_workflow.py",
        "src/backend/forecast_workbench_context.py",
    ]

    offenders = {
        module_path: sorted(
            _imports_from(module_path, "src.backend.operational_views") & amount_helpers
        )
        for module_path in phase_one_modules
    }
    offenders = {module_path: names for module_path, names in offenders.items() if names}

    assert offenders == {}


def test_operational_views_module_has_been_retired():
    assert not (PROJECT_ROOT / "src/backend/operational_views.py").exists()


def test_no_runtime_or_unit_tests_import_operational_views():
    offenders: list[str] = []
    for base in [PROJECT_ROOT / "src", PROJECT_ROOT / "tests"]:
        for path in base.rglob("*.py"):
            if path == Path(__file__).resolve():
                continue
            source = path.read_text(encoding="utf-8")
            if "operational_views" in source:
                offenders.append(str(path.relative_to(PROJECT_ROOT)))

    assert offenders == []


def test_app_imports_forecast_context_builder_from_canonical_module():
    operational_imports = _imports_from("src/backend/app.py", "src.backend.operational_views")
    canonical_imports = _imports_from(
        "src/backend/app.py", "src.backend.forecast_workbench_context"
    )

    assert "build_forecast_page_context" not in operational_imports
    assert "build" in canonical_imports


def test_forecast_context_builder_signature_has_no_data_base_path_argument():
    from src.backend.forecast_workbench_context import build

    parameters = inspect.signature(build).parameters

    assert "data_base_path" not in parameters
    assert list(parameters)[:3] == ["forecast_config", "db", "target_source"]


def test_backend_app_has_no_module_level_flask_app_instance():
    tree = ast.parse((PROJECT_ROOT / "src/backend/app.py").read_text(encoding="utf-8"))

    module_level_app_factories = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
        and target.id == "app"
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "create_app"
    ]

    assert module_level_app_factories == []


def test_forecast_engine_does_not_keep_dead_month_filter_helpers():
    tree = ast.parse((PROJECT_ROOT / "src/backend/forecast_engine.py").read_text(encoding="utf-8"))
    defined_functions = {
        node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
    }

    assert {"_month_quantity", "_month_amount"}.isdisjoint(defined_functions)


def test_dashboard_analytics_helpers_are_imported_from_analytics_not_operational_views():
    dashboard_helpers = {
        "aggregate_to_analytics",
        "build_customer_risk_ranking",
        "build_status_distribution",
    }
    phase_three_modules = [
        "src/backend/app.py",
        "src/backend/dashboard_analytics_workflow.py",
    ]

    offenders = {
        module_path: sorted(
            _imports_from(module_path, "src.backend.operational_views") & dashboard_helpers
        )
        for module_path in phase_three_modules
    }
    offenders = {module_path: names for module_path, names in offenders.items() if names}

    assert offenders == {}


def test_forecast_page_presentation_helpers_are_not_route_local():
    forbidden_defs = {
        "_forecast_row_risk",
        "_risk_levels",
        "_forecast_signature",
        "_validate_forecast_signature",
    }
    tree = ast.parse(
        (PROJECT_ROOT / "src/backend/app.py").read_text(encoding="utf-8")
    )

    defined_functions = {
        node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
    }

    assert defined_functions & forbidden_defs == set()


def test_app_imports_forecast_page_render_context_from_canonical_module():
    canonical_imports = _imports_from("src/backend/app.py", "src.backend.forecast_page_context")

    assert "build_forecast_page_render_context" in canonical_imports
    assert "validate_forecast_signature" in canonical_imports


def test_monthly_review_routes_use_context_builder():
    forbidden_imports = {
        "build_monthly_review",
        "build_action_lists",
        "build_customer_summary",
        "build_product_summary",
        "build_forecast_bias",
        "build_trend",
        "build_trend_chart",
    }
    app_imports = set()
    for module_name in [
        "src.backend.monthly_review",
        "src.backend.monthly_review_actions",
        "src.backend.monthly_review_chart",
        "src.backend.monthly_review_customers",
        "src.backend.monthly_review_forecast_bias",
        "src.backend.monthly_review_products",
        "src.backend.monthly_review_trend",
    ]:
        app_imports.update(_imports_from("src/backend/app.py", module_name))

    assert app_imports & forbidden_imports == set()
    assert "build_monthly_review_context" in _imports_from(
        "src/backend/app.py", "src.backend.monthly_review_context"
    )


def test_settings_route_uses_settings_context_builder():
    data_validator_imports = _imports_from("src/backend/app.py", "src.backend.data_validator")
    settings_imports = _imports_from("src/backend/app.py", "src.backend.settings_context")

    assert "validate_budget_coverage" not in data_validator_imports
    assert "validate_health" not in data_validator_imports
    assert "build_settings_page_context" in settings_imports
    assert "build_settings_error_context" in settings_imports

    app_source = (PROJECT_ROOT / "src/backend/app.py").read_text(encoding="utf-8")
    assert "SELECT DISTINCT product_code FROM budget_targets" not in app_source


def test_forecast_context_uses_workbench_input_interface_not_raw_maps():
    source = (PROJECT_ROOT / "src/backend/forecast_workbench_context.py").read_text(encoding="utf-8")
    forbidden = [
        "inputs.item_configs",
        "inputs.excluded_item_ids",
        "inputs.manual_adjustments",
        "inputs.adjustment_reasons",
        "inputs.budget_targets",
        "inputs.budget_year_map",
        "inputs.budget_year_amount_map",
        "inputs.budget_months",
    ]

    assert [name for name in forbidden if name in source] == []


def test_monthly_review_source_table_sql_stays_in_data_reader():
    allowed = PROJECT_ROOT / "src/backend/monthly_review_data.py"
    table_names = [
        "daily_sales_actuals",
        "sales_records",
        "budget_targets",
        "snapshot_items",
        "month_close_records",
        "item_configs",
        "current_month_records",
    ]
    offenders: dict[str, list[str]] = {}
    for path in (PROJECT_ROOT / "src/backend").glob("monthly_review*.py"):
        if path == allowed:
            continue
        source = path.read_text(encoding="utf-8")
        matches = [table for table in table_names if table in source]
        if matches:
            offenders[str(path.relative_to(PROJECT_ROOT))] = matches

    assert offenders == {}


def test_forecast_context_delegates_product_monitor_month_orchestration():
    source = (PROJECT_ROOT / "src/backend/forecast_workbench_context.py").read_text(encoding="utf-8")
    forbidden = [
        "batch_project_eom",
        "ensure_calendar_year",
        "build_dashboard_metrics",
        "build_product_monitor_rows",
    ]

    assert [name for name in forbidden if name in source] == []
    assert "build_product_monitor_month_context" in source
