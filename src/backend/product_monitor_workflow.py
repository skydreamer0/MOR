from __future__ import annotations

from typing import Any

from src.backend.daily_sales_importer import get_close_record, get_latest_import_batch


def build_product_monitor_template_context(
    context,
    db,
    *,
    fallback_year: int,
    fallback_month: int,
    error_message: str | None = None,
    import_message: str | None = None,
    import_error: str | None = None,
) -> dict[str, Any]:
    year = context.target.year if context else fallback_year
    month = context.target.month if context else fallback_month
    return {
        "year": year,
        "month": month,
        "rows": context.monitor_rows if context else [],
        "error_message": error_message,
        "import_message": import_message,
        "import_error": import_error,
        "latest_batch": get_latest_import_batch(db, year, month) if year and month else None,
        "close_record": get_close_record(db, year, month) if year and month else None,
    }
