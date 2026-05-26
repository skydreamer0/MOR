from dataclasses import dataclass

from src.backend.database import get_db
from src.backend.product_monitor_workflow import build_product_monitor_template_context


@dataclass(frozen=True)
class _Target:
    year: int
    month: int


@dataclass(frozen=True)
class _Context:
    target: _Target
    monitor_rows: list


def test_build_product_monitor_template_context_uses_context_period_and_rows(tmp_path):
    db = get_db(tmp_path)
    context = _Context(target=_Target(year=2026, month=5), monitor_rows=["row-a"])

    result = build_product_monitor_template_context(
        context,
        db,
        fallback_year=0,
        fallback_month=0,
        import_message="imported",
        import_error=None,
    )

    assert result == {
        "year": 2026,
        "month": 5,
        "rows": ["row-a"],
        "error_message": None,
        "import_message": "imported",
        "import_error": None,
        "latest_batch": None,
        "close_record": None,
    }


def test_build_product_monitor_template_context_preserves_fallback_when_context_missing(tmp_path):
    db = get_db(tmp_path)

    result = build_product_monitor_template_context(
        None,
        db,
        fallback_year=2026,
        fallback_month=5,
        error_message="load failed",
        import_message=None,
        import_error="bad import",
    )

    assert result["year"] == 2026
    assert result["month"] == 5
    assert result["rows"] == []
    assert result["error_message"] == "load failed"
    assert result["import_error"] == "bad import"
    assert result["latest_batch"] is None
    assert result["close_record"] is None
