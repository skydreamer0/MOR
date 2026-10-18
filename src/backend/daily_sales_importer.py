from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO

import pandas as pd

from src.backend.database import MORDatabase
from src.backend.row_identity import make_row_id


# Maps internal field names → Chinese column headers in the workbook
DAILY_SALES_COLUMNS = {
    "sales_date": "出貨日期",
    "customer_code": "客戶代號",
    "customer_name": "客戶簡稱",
    "product_code": "產品",
    "product_name": "產品簡稱",
    "sales_quantity": "銷售數量",
    "gift_quantity": "贈品數量",
    "net_unit_price": "銷貨淨價",
    "taxed_amount": "含稅淨額",
    "bonus_basis_amount": "折後業績",
    "invoice_number": "發票編號",
    "shipment_number": "出貨單號",
    "order_type": "單別",
    "performance_type": "業績屬性",
}


@dataclass(frozen=True)
class DailySalesImportResult:
    batch_id: int
    sales_year: int
    sales_month: int
    row_count: int
    date_start: object
    date_end: object
    quantity_total: float
    taxed_amount_total: float


@dataclass(frozen=True)
class DailyActualAggregate:
    actual_quantity: float
    taxed_amount: float
    latest_sales_date: object | None


def normalize_daily_sales(raw: pd.DataFrame) -> pd.DataFrame:
    from src.backend.import_normalization import normalize_monitor
    return normalize_monitor(raw)


def import_daily_sales_workbook(db: MORDatabase, file_obj: BinaryIO, source_filename: str,
                                *, complete_months=None, daily_partitions=False) -> DailySalesImportResult:
    return import_daily_sales_workbooks(db, [(source_filename, file_obj.read())],
                                       complete_months=complete_months, daily_partitions=daily_partitions)


def import_daily_sales_workbooks(db, files, *, complete_months=None, daily_partitions=False):
    from src.backend.import_service import preflight, commit_plan
    plan = preflight(files, intent='monitor', complete_months=complete_months, daily_partitions=daily_partitions)
    normalized = plan.frames['monitor']
    result = commit_plan(db, plan)
    return DailySalesImportResult(
        batch_id=result['batch_id'], sales_year=int(normalized.sales_year.iloc[0]),
        sales_month=int(normalized.sales_month.iloc[0]), row_count=len(normalized),
        date_start=normalized.sales_date.min(), date_end=normalized.sales_date.max(),
        quantity_total=float(normalized.actual_quantity.sum()),
        taxed_amount_total=float(normalized.taxed_amount.sum()),
    )


def fetch_daily_actuals_by_row_id(
    db: MORDatabase,
    year: int,
    month: int,
) -> dict[str, DailyActualAggregate]:
    """Return per-row aggregates keyed by canonical forecast row ID for the given month."""
    with db.get_connection() as conn:
        rows = conn.execute(
            """
            SELECT customer_name,
                   product_code,
                   SUM(actual_quantity)  AS actual_quantity,
                   SUM(taxed_amount)     AS taxed_amount,
                   MAX(sales_date)       AS latest_sales_date
            FROM daily_sales_actuals
            WHERE sales_year = ? AND sales_month = ?
            GROUP BY customer_name, product_code
            """,
            (year, month),
        ).fetchall()
    return {
        make_row_id(row["customer_name"], row["product_code"]): DailyActualAggregate(
            actual_quantity=float(row["actual_quantity"] or 0),
            taxed_amount=float(row["taxed_amount"] or 0),
            latest_sales_date=row["latest_sales_date"],
        )
        for row in rows
    }


def is_month_closed(db: MORDatabase, year: int, month: int) -> bool:
    """Return True if a close record exists for the given year/month."""
    with db.get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM month_close_records WHERE year = ? AND month = ?",
            (year, month),
        ).fetchone()
    return row is not None


def close_month(
    db: MORDatabase,
    year: int,
    month: int,
    snapshot_id: int | None = None,
    note: str | None = None,
) -> None:
    """Lock the given year/month, preventing further imports.

    snapshot_id: ID of the forecast snapshot saved at close time (for Phase 7 review).
    Raises ValueError if already closed or if no actuals data exists.
    """
    with db.get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        if conn.execute('SELECT 1 FROM month_close_records WHERE year=? AND month=?',(year,month)).fetchone():
            raise ValueError(f"{year}/{month:02d} 已結月，無法重複結月。")
        summary = conn.execute(
            """
            SELECT COUNT(*)                          AS row_count,
                   COALESCE(SUM(actual_quantity), 0) AS qty_total,
                   COALESCE(SUM(taxed_amount), 0)    AS amount_total
            FROM   daily_sales_actuals
            WHERE  sales_year = ? AND sales_month = ?
            """,
            (year, month),
        ).fetchone()
        if summary["row_count"] == 0:
            raise ValueError(f"{year}/{month:02d} 尚無匯入資料，無法結月。")
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
        conn.commit()


def get_latest_import_batch(db: MORDatabase, year: int, month: int) -> dict | None:
    """Return the latest import batch summary for the given month, or None."""
    with db.get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, source_filename, imported_at,
                   row_count, quantity_total, taxed_amount_total, status
            FROM   daily_import_batches
            WHERE  sales_year = ? AND sales_month = ?
            ORDER  BY id DESC LIMIT 1
            """,
            (year, month),
        ).fetchone()
    return dict(row) if row else None


def get_close_record(db: MORDatabase, year: int, month: int) -> dict | None:
    """Return the close record for the given month, or None."""
    with db.get_connection() as conn:
        row = conn.execute(
            """
            SELECT year, month, closed_at, final_snapshot_id,
                   actual_row_count, actual_quantity_total, actual_amount_total, note
            FROM   month_close_records
            WHERE  year = ? AND month = ?
            """,
            (year, month),
        ).fetchone()
    return dict(row) if row else None


def list_closed_months(db: MORDatabase) -> list[tuple[int, int]]:
    """Return all closed (year, month) pairs sorted descending."""
    with db.get_connection() as conn:
        rows = conn.execute(
            "SELECT year, month FROM month_close_records ORDER BY year DESC, month DESC"
        ).fetchall()
    return [(r["year"], r["month"]) for r in rows]
