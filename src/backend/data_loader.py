from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.backend.forecast_config import ForecastConfig
from src.backend.forecast_models import ForecastTarget


def load_sales_detail(base_path: Path, config: ForecastConfig | None = None) -> pd.DataFrame:
    config = config or ForecastConfig()
    file_path = base_path / config.detail_file
    if not file_path.exists():
        raise FileNotFoundError(f"找不到業績明細檔案: {file_path}")
    data = pd.read_excel(file_path, sheet_name=config.detail_sheet)
    return prepare_sales_data(data, config)


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


def default_target_from_data(data: pd.DataFrame, config: ForecastConfig | None = None) -> ForecastTarget:
    prepared = prepare_sales_data(data, config)
    latest = prepared["order_date"].max().date()
    if latest.month == 12:
        return ForecastTarget(latest.year + 1, 1)
    return ForecastTarget(latest.year, latest.month + 1)
