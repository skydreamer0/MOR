from __future__ import annotations

import ast
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


def test_operational_views_no_longer_exports_amount_facades():
    forbidden_defs = {
        "forecast_amount_total",
        "last_year_amount_total",
        "recalculate_forecast_amounts",
    }
    tree = ast.parse(
        (PROJECT_ROOT / "src/backend/operational_views.py").read_text(encoding="utf-8")
    )

    defined_functions = {
        node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
    }

    assert defined_functions & forbidden_defs == set()


def test_app_imports_forecast_context_builder_from_canonical_module():
    operational_imports = _imports_from("src/backend/app.py", "src.backend.operational_views")
    canonical_imports = _imports_from(
        "src/backend/app.py", "src.backend.forecast_workbench_context"
    )

    assert "build_forecast_page_context" not in operational_imports
    assert "build" in canonical_imports


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


def test_operational_views_no_longer_exports_dashboard_analytics_helpers():
    forbidden_defs = {
        "aggregate_to_analytics",
        "build_customer_risk_ranking",
        "build_status_distribution",
    }
    tree = ast.parse(
        (PROJECT_ROOT / "src/backend/operational_views.py").read_text(encoding="utf-8")
    )

    defined_functions = {
        node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
    }

    assert defined_functions & forbidden_defs == set()


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
