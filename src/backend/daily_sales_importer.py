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


def _number(values: pd.Series) -> pd.Series:
    return pd.to_numeric(values, errors="coerce").fillna(0)


def _require_columns(raw: pd.DataFrame, columns) -> None:
    missing = [col for col in columns if col not in raw.columns]
    if missing:
        raise ValueError(f"每日業績檔缺少欄位: {', '.join(missing)}")
