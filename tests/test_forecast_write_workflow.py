from pathlib import Path

from src.backend.database import MORDatabase
from src.backend.forecast_write_workflow import save_row_override
from src.backend.row_identity import make_row_id


def test_save_row_override_decodes_canonical_row_identity(tmp_path: Path):
    db = MORDatabase(tmp_path / "mor_workbench.db")
    row_id = make_row_id("A__B", "C")

    save_row_override(db, row_id, "12.7", "Review", 2026, 5)

    with db.get_connection() as conn:
        row = conn.execute(
            """
            SELECT customer_name, product_code, manual_quantity, adjustment_reason
            FROM forecast_adjustments
            WHERE year = 2026 AND month = 5
            """
        ).fetchone()

    assert dict(row) == {
        "customer_name": "A__B",
        "product_code": "C",
        "manual_quantity": 12,
        "adjustment_reason": "Review",
    }
