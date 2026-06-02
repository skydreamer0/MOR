"""Close-month workflow: snapshot creation and month-close record in one transaction.

Replaces the two-step pattern in app.py (_find_or_create_close_snapshot then
close_month) that could leave an orphaned snapshot when the second step failed.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from src.backend.daily_sales_importer import is_month_closed
from src.backend.database import MORDatabase

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CloseMonthResult:
    snapshot_id: int
    message: str


def execute_close_month(
    db: MORDatabase,
    year: int,
    month: int,
    snapshot_rows: list[dict],
    note: str | None = None,
) -> CloseMonthResult:
    """Create close-month snapshot and month_close_record atomically.

    Both the snapshot insert and the close-record insert share one connection so
    that a failure after the snapshot write does not leave an orphaned snapshot.

    Args:
        snapshot_rows: serialized forecast rows (from serialize_forecast_rows_for_snapshot).
        note: optional operator note stored on the close record.

    Raises:
        ValueError: if the month is already closed or has no actuals data.
    """
    if is_month_closed(db, year, month):
        raise ValueError(f"{year}/{month:02d} 已結月，無法重複結月。")

    with db.get_connection() as conn:
        summary = conn.execute(
            """
            SELECT COUNT(*)                          AS row_count,
                   COALESCE(SUM(actual_quantity), 0) AS qty_total,
                   COALESCE(SUM(taxed_amount),    0) AS amount_total
            FROM   daily_sales_actuals
            WHERE  sales_year = ? AND sales_month = ?
            """,
            (year, month),
        ).fetchone()
        if summary["row_count"] == 0:
            raise ValueError(f"{year}/{month:02d} 尚無匯入資料，無法結月。")

        # Reuse existing CloseMonth snapshot if already created (idempotent).
        existing = conn.execute(
            """
            SELECT id FROM forecast_snapshots
            WHERE year = ? AND month = ? AND snapshot_type = 'CloseMonth'
            ORDER BY id DESC LIMIT 1
            """,
            (year, month),
        ).fetchone()

        if existing:
            snapshot_id = existing["id"]
        else:
            cursor = conn.execute(
                """
                INSERT INTO forecast_snapshots
                    (snapshot_name, snapshot_type, year, month, created_by)
                VALUES (?, 'CloseMonth', ?, ?, '結月')
                """,
                (f"結月快照 {year}/{month:02d}", year, month),
            )
            snapshot_id = cursor.lastrowid
            for row in snapshot_rows:
                conn.execute(
                    """
                    INSERT INTO snapshot_items
                        (snapshot_id, customer_name, product_code,
                         system_forecast, manual_adjustment, final_forecast)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        snapshot_id,
                        row["customer_name"],
                        row["product_code"],
                        row.get("system_forecast", 0),
                        row.get("manual_adjustment"),
                        row.get("final_forecast", 0),
                    ),
                )

        batch_row = conn.execute(
            """
            SELECT id FROM daily_import_batches
            WHERE  sales_year = ? AND sales_month = ?
            ORDER  BY id DESC LIMIT 1
            """,
            (year, month),
        ).fetchone()

        conn.execute(
            """
            INSERT INTO month_close_records
                (year, month, source_batch_id, actual_row_count,
                 actual_quantity_total, actual_amount_total, note, final_snapshot_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                year, month,
                batch_row["id"] if batch_row else None,
                summary["row_count"],
                summary["qty_total"],
                summary["amount_total"],
                note,
                snapshot_id,
            ),
        )

    return CloseMonthResult(
        snapshot_id=snapshot_id,
        message=f"{year}/{month:02d} 結月完成。",
    )
