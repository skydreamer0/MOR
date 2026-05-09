from __future__ import annotations

import hashlib
from dataclasses import dataclass
from io import BytesIO
from typing import BinaryIO

import pandas as pd

from src.backend.data_loader import normalize_product_code
from src.backend.database import MORDatabase


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
    """Parse and filter a raw daily-sales DataFrame.

    Drops summary/incomplete rows (missing date, customer, or product).
    Raises ValueError if the workbook is empty or spans multiple months.
    """
    _require_columns(raw, DAILY_SALES_COLUMNS.values())
    sales_date = pd.to_datetime(raw[DAILY_SALES_COLUMNS["sales_date"]], errors="coerce")
    normalized = pd.DataFrame(
        {
            "sales_year": sales_date.dt.year,
            "sales_month": sales_date.dt.month,
            "sales_date": sales_date.dt.date,
            "customer_code": raw[DAILY_SALES_COLUMNS["customer_code"]].fillna("").astype(str).str.strip(),
            "customer_name": raw[DAILY_SALES_COLUMNS["customer_name"]].fillna("").astype(str).str.strip(),
            "product_code": raw[DAILY_SALES_COLUMNS["product_code"]].map(normalize_product_code),
            "product_name": raw[DAILY_SALES_COLUMNS["product_name"]].fillna("").astype(str).str.strip(),
            "sales_quantity": _number(raw[DAILY_SALES_COLUMNS["sales_quantity"]]),
            "gift_quantity": _number(raw[DAILY_SALES_COLUMNS["gift_quantity"]]),
            "net_unit_price": _number(raw[DAILY_SALES_COLUMNS["net_unit_price"]]),
            "taxed_amount": _number(raw[DAILY_SALES_COLUMNS["taxed_amount"]]),
            "bonus_basis_amount": _number(raw[DAILY_SALES_COLUMNS["bonus_basis_amount"]]),
            "invoice_number": raw[DAILY_SALES_COLUMNS["invoice_number"]].fillna("").astype(str).str.strip(),
            "shipment_number": raw[DAILY_SALES_COLUMNS["shipment_number"]].fillna("").astype(str).str.strip(),
            "order_type": raw[DAILY_SALES_COLUMNS["order_type"]].fillna("").astype(str).str.strip(),
            "performance_type": raw[DAILY_SALES_COLUMNS["performance_type"]].fillna("").astype(str).str.strip(),
        }
    )
    normalized["actual_quantity"] = normalized["sales_quantity"] + normalized["gift_quantity"]
    # Drop rows that lack the three required keys (summary rows and incomplete entries)
    normalized = normalized[
        normalized["sales_date"].notna()
        & normalized["customer_name"].astype(bool)
        & normalized["product_code"].astype(bool)
    ].copy()
    if normalized.empty:
        raise ValueError("每日業績檔沒有可匯入的明細列。")
    months = normalized[["sales_year", "sales_month"]].drop_duplicates()
    if len(months) != 1:
        raise ValueError("每日業績檔不可混用多個月份。")
    return normalized


def import_daily_sales_workbook(
    db: MORDatabase,
    file_obj: BinaryIO,
    source_filename: str,
) -> DailySalesImportResult:
    """Import a cumulative monthly sales workbook, overwriting any prior data for the same month."""
    payload = file_obj.read()
    source_hash = hashlib.sha256(payload).hexdigest()
    raw = pd.read_excel(BytesIO(payload))
    normalized = normalize_daily_sales(raw)
    year = int(normalized["sales_year"].iloc[0])
    month = int(normalized["sales_month"].iloc[0])
    if is_month_closed(db, year, month):
        raise ValueError(f"{year}/{month:02d} 已結月，不可覆蓋。如需修改請先解除結月。")
    date_start = normalized["sales_date"].min()
    date_end = normalized["sales_date"].max()
    quantity_total = float(normalized["actual_quantity"].sum())
    taxed_amount_total = float(normalized["taxed_amount"].sum())

    with db.get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO daily_import_batches
            (source_filename, source_hash, sales_year, sales_month, row_count,
             date_start, date_end, quantity_total, taxed_amount_total, status, message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'success', ?)
            """,
            (
                source_filename,
                source_hash,
                year,
                month,
                int(len(normalized)),
                str(date_start),
                str(date_end),
                quantity_total,
                taxed_amount_total,
                "匯入完成",
            ),
        )
        batch_id = int(cursor.lastrowid)
        # Same-month overwrite: delete previous snapshot before inserting new one
        conn.execute(
            "DELETE FROM daily_sales_actuals WHERE sales_year = ? AND sales_month = ?",
            (year, month),
        )
        rows = normalized.copy()
        rows["import_batch_id"] = batch_id
        rows[
            [
                "sales_year", "sales_month", "sales_date", "customer_code",
                "customer_name", "product_code", "product_name", "sales_quantity",
                "gift_quantity", "actual_quantity", "net_unit_price", "taxed_amount",
                "bonus_basis_amount", "invoice_number", "shipment_number",
                "order_type", "performance_type", "import_batch_id",
            ]
        ].to_sql("daily_sales_actuals", conn, if_exists="append", index=False)
        conn.commit()

    return DailySalesImportResult(
        batch_id=batch_id,
        sales_year=year,
        sales_month=month,
        row_count=int(len(normalized)),
        date_start=date_start,
        date_end=date_end,
        quantity_total=quantity_total,
        taxed_amount_total=taxed_amount_total,
    )


def fetch_daily_actuals_by_row_id(
    db: MORDatabase,
    year: int,
    month: int,
) -> dict[str, DailyActualAggregate]:
    """Return per-row aggregates (customer__product) for the given month."""
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
        f"{row['customer_name']}__{row['product_code']}": DailyActualAggregate(
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
    if is_month_closed(db, year, month):
        raise ValueError(f"{year}/{month:02d} 已結月，無法重複結月。")
    with db.get_connection() as conn:
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


def _number(values: pd.Series) -> pd.Series:
    return pd.to_numeric(values, errors="coerce").fillna(0)


def _require_columns(raw: pd.DataFrame, columns) -> None:
    missing = [col for col in columns if col not in raw.columns]
    if missing:
        raise ValueError(f"每日業績檔缺少欄位: {', '.join(missing)}")
