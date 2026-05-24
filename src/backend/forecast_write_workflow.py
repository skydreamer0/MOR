from __future__ import annotations

from src.backend.web.form_parser import FormValidationError


def save_row_override(
    db,
    row_id: str,
    manual_qty: str | None,
    reason: str | None,
    year: int,
    month: int,
    *,
    updated_by: str = "User",
) -> None:
    customer, product_code = row_id.split("__", 1)
    try:
        val = int(float(manual_qty)) if manual_qty and manual_qty.strip() else None
    except ValueError as exc:
        raise FormValidationError("Invalid quantity") from exc

    with db.get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO forecast_adjustments
            (year, month, customer_name, product_code, manual_quantity, adjustment_reason, updated_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (year, month, customer, product_code, val, reason, updated_by),
        )
        conn.commit()
