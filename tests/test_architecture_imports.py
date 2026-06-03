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
