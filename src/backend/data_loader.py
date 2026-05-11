"""Data Loader — 讀取並合併業績資料供 forecast_engine 使用。

正常頁面請求與匯出使用 load_sales_detail_from_db()，從 SQLite 讀取。
Excel 只在同步/匯入流程（/sync, /upload/current-month, /monitor/products/import）使用。
架構背景詳見 docs/architecture/current-month-data-integration.md。
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from src.backend.forecast_config import ForecastConfig
from src.backend.forecast_models import ForecastTarget

if TYPE_CHECKING:
    from src.backend.database import MORDatabase

_SALES_COLUMNS = [
    "order_date", "customer_name", "product_code", "product_name",
    "quantity", "unit_price", "amount",
]
_RENAME_MAP = {
    "customer_name": "客戶簡稱",
    "product_code":  "商品號",
    "product_name":  "商品簡稱",
    "quantity":      "銷+贈S量",
    "unit_price":    "單價NT(淨)",
    "amount":        "含稅總額(淨)",
}
_REQUIRED_CHINESE_COLS = (
    "年", "月", "日", "客戶簡稱", "商品號", "商品簡稱",
    "銷+贈S量", "單價NT(淨)", "含稅總額(淨)", "order_date",
)


def load_sales_detail_from_db(db: "MORDatabase") -> pd.DataFrame:
    """讀取 sales_records + current_month_records，回傳與業績明細相同格式的 DataFrame。

    這是頁面請求與匯出的主要資料來源。不讀取 Excel。
    若 DB 無資料，回傳具有正確欄位的空 DataFrame。
    """
    with db.get_connection() as conn:
        rows = conn.execute(
            "SELECT order_date, customer_name, product_code, product_name, "
            "quantity, unit_price, amount FROM sales_records "
            "UNION ALL "
            "SELECT order_date, customer_name, product_code, product_name, "
            "quantity, unit_price, amount FROM current_month_records"
        ).fetchall()

    if not rows:
        return _empty_sales_dataframe()

    df = pd.DataFrame(rows, columns=_SALES_COLUMNS)
    return _normalize_db_sales_df(df)


def default_target_from_db(db: "MORDatabase") -> ForecastTarget:
    """從 DB 取得預設預估目標月份（不讀取 Excel）。

    查詢 sales_records 和 current_month_records 的最新 order_date，
    回傳下一個月份為預設目標。若無資料則以今日推算。
    """
    with db.get_connection() as conn:
        row = conn.execute(
            "SELECT MAX(d) AS max_date FROM ("
            "  SELECT order_date AS d FROM sales_records "
            "  UNION ALL "
            "  SELECT order_date AS d FROM current_month_records"
            ")"
        ).fetchone()

    max_date_str = row["max_date"] if row else None
    if not max_date_str:
        from datetime import date as _date
        today = _date.today()
        return ForecastTarget(today.year, today.month)

    latest = pd.Timestamp(max_date_str).date()
    if latest.month == 12:
        return ForecastTarget(latest.year + 1, 1)
    return ForecastTarget(latest.year, latest.month + 1)


def _normalize_db_sales_df(df: pd.DataFrame) -> pd.DataFrame:
    """英文欄位名稱 → 中文，補上年/月/日，正規化商品號，清除無效列。"""
    df = df.copy()
    # sales_records stores date strings ('2026-03-10'), current_month_records stores
    # datetime strings ('2026-05-05 00:00:00'); format='mixed' handles both safely.
    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce", format="mixed")
    df = df.dropna(subset=["order_date"]).copy()
    df["年"] = df["order_date"].dt.year.astype(int)
    df["月"] = df["order_date"].dt.month.astype(int)
    df["日"] = df["order_date"].dt.day.astype(int)
    df = df.rename(columns=_RENAME_MAP)
    df["商品號"] = df["商品號"].map(normalize_product_code)
    return df.dropna(subset=["客戶簡稱", "商品號"]).reset_index(drop=True)


def _empty_sales_dataframe() -> pd.DataFrame:
    return pd.DataFrame(columns=list(_REQUIRED_CHINESE_COLS))


def load_sales_detail(
    base_path: Path,
    config: ForecastConfig | None = None,
    db: "MORDatabase | None" = None,
) -> pd.DataFrame:
    """讀取歷史業績明細，若有提供 db 則合併當月 SHPB 資料。

    Args:
        base_path: 業績明細 Excel 所在目錄（通常為 PROJECT_ROOT）。
        config:    ForecastConfig，決定要讀哪支 Excel。
        db:        MORDatabase 實例。若為 None 則只讀 Excel（向後相容）。

    Returns:
        正規化後的 DataFrame，已加入 order_date、年、月、日等欄位，
        可直接傳入 forecast_engine.build_forecast()。
    """
    config = config or ForecastConfig()
    file_path = base_path / config.detail_file
    if not file_path.exists():
        raise FileNotFoundError(f"找不到業績明細檔案: {file_path}")

    historical = prepare_sales_data(pd.read_excel(file_path, sheet_name=config.detail_sheet), config)

    if db is None:
        return historical

    current = _load_current_month_from_db(db)
    if current.empty:
        return historical

    # 兩者時間不重疊（Excel 只到上月底，DB 只存當月），直接 concat 不會重複
    return pd.concat([historical, current], ignore_index=True)


def prepare_sales_data(data: pd.DataFrame, config: ForecastConfig | None = None) -> pd.DataFrame:
    config = config or ForecastConfig()
    missing = [column for column in config.required_columns if column not in data.columns]
    if missing:
        raise ValueError(f"業績明細缺少欄位: {', '.join(missing)}")

    prepared = data.copy()
    prepared["商品號"] = prepared["商品號"].map(normalize_product_code)
    prepared["銷+贈S量"]   = pd.to_numeric(prepared["銷+贈S量"],   errors="coerce").fillna(0)
    prepared["單價NT(淨)"] = pd.to_numeric(prepared["單價NT(淨)"], errors="coerce").fillna(0)
    prepared["含稅總額(淨)"] = pd.to_numeric(prepared["含稅總額(淨)"], errors="coerce").fillna(0)
    prepared["order_date"] = pd.to_datetime(
        {
            "year": pd.to_numeric(prepared["年"], errors="coerce"),
            "month": pd.to_numeric(prepared["月"], errors="coerce"),
            "day": pd.to_numeric(prepared["日"], errors="coerce"),
        },
        errors="coerce",
    )
    return prepared.dropna(subset=["order_date", "客戶簡稱", "商品號"])


def normalize_product_code(value: object) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(value).strip()
    if text.endswith(".0"):
        head = text[:-2]
        if head.isdigit():
            return head
    return text


def _load_current_month_from_db(db: "MORDatabase") -> pd.DataFrame:
    """從 current_month_records 讀取當月資料，轉換為與業績明細相同的欄位格式。

    供 load_sales_detail（Excel+DB 合併路徑）使用；頁面請求改用 load_sales_detail_from_db。
    """
    with db.get_connection() as conn:
        rows = conn.execute(
            "SELECT order_date, customer_name, product_code, product_name, "
            "quantity, unit_price, amount FROM current_month_records"
        ).fetchall()

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=_SALES_COLUMNS)
    return _normalize_db_sales_df(df)


def default_target_from_data(data: pd.DataFrame, config: ForecastConfig | None = None) -> ForecastTarget:
    prepared = prepare_sales_data(data, config)
    latest = prepared["order_date"].max().date()
    if latest.month == 12:
        return ForecastTarget(latest.year + 1, 1)
    return ForecastTarget(latest.year, latest.month + 1)


def latest_closed_month_from_data(data: pd.DataFrame, config: ForecastConfig | None = None) -> ForecastTarget:
    prepared = prepare_sales_data(data, config)
    latest = prepared["order_date"].max().date()
    return ForecastTarget(latest.year, latest.month)
