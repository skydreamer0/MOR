"""Tests for current-month SHPB data integration (Stage 1-5).

Covers:
- normalize_shpb_records: SHPB column mapping and date parsing
- import_current_month: write / replace by month
- _clear_covered_current_month_records: auto-cleanup after sync
- load_sales_detail with db: merges Excel history + current_month_records
"""
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from src.backend.database import MORDatabase
from src.backend.etl import (
    import_current_month,
    normalize_shpb_records,
    normalize_sales_records,
    SHPB_COLUMNS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db() -> MORDatabase:
    tmp = tempfile.mkstemp(suffix=".db")[1]
    return MORDatabase(Path(tmp))


def _shpb_row(**overrides) -> dict:
    """最小有效的 SHPB 資料列，可透過 overrides 覆蓋任意欄位。"""
    base = {
        SHPB_COLUMNS["order_date"]:    "20260505",
        SHPB_COLUMNS["customer_name"]: "慈濟台北",
        SHPB_COLUMNS["product_code"]:  "T5EL1",
        SHPB_COLUMNS["product_name"]:  "ELI 22.5癌立佳",
        SHPB_COLUMNS["sales_qty"]:     10,
        SHPB_COLUMNS["gift_qty"]:      2,
        SHPB_COLUMNS["unit_price"]:    5688.83,
        SHPB_COLUMNS["amount"]:        68266.0,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# normalize_shpb_records
# ---------------------------------------------------------------------------

def test_normalize_shpb_maps_columns_correctly():
    df = pd.DataFrame([_shpb_row()])
    result = normalize_shpb_records(df)

    assert len(result) == 1
    row = result.iloc[0]
    assert row["customer_name"] == "慈濟台北"
    assert row["product_code"] == "T5EL1"
    assert row["quantity"] == 12          # 銷售10 + 贈品2
    assert row["unit_price"] == 5688.83
    assert row["order_date"].year == 2026
    assert row["order_date"].month == 5
    assert row["order_date"].day == 5


def test_normalize_shpb_sums_sales_and_gift_qty():
    df = pd.DataFrame([_shpb_row(**{
        SHPB_COLUMNS["sales_qty"]: 15,
        SHPB_COLUMNS["gift_qty"]:  5,
    })])
    result = normalize_shpb_records(df)
    assert result.iloc[0]["quantity"] == 20


def test_normalize_shpb_drops_invalid_dates():
    rows = [
        _shpb_row(**{SHPB_COLUMNS["order_date"]: "20260505"}),
        _shpb_row(**{SHPB_COLUMNS["order_date"]: "invalid"}),
    ]
    result = normalize_shpb_records(pd.DataFrame(rows))
    assert len(result) == 1


def test_normalize_shpb_raises_on_missing_columns():
    df = pd.DataFrame([{"出貨日期": "20260505"}])  # 缺很多欄
    with pytest.raises(ValueError, match="Missing columns"):
        normalize_shpb_records(df)


# ---------------------------------------------------------------------------
# import_current_month
# ---------------------------------------------------------------------------

def test_import_current_month_writes_to_db():
    db = _make_db()
    df = pd.DataFrame([_shpb_row()])
    count = import_current_month(db, df)
    assert count == 1

    with db.get_connection() as conn:
        rows = conn.execute("SELECT * FROM current_month_records").fetchall()
    assert len(rows) == 1
    assert rows[0]["customer_name"] == "慈濟台北"
    assert rows[0]["quantity"] == 12


def test_import_current_month_replaces_same_month_on_reupload():
    """重複上傳同月份資料時，舊資料應被完整取代。"""
    db = _make_db()
    df_first = pd.DataFrame([_shpb_row(**{SHPB_COLUMNS["sales_qty"]: 10, SHPB_COLUMNS["gift_qty"]: 0})])
    import_current_month(db, df_first)

    df_second = pd.DataFrame([_shpb_row(**{SHPB_COLUMNS["sales_qty"]: 20, SHPB_COLUMNS["gift_qty"]: 0})])
    import_current_month(db, df_second)

    with db.get_connection() as conn:
        rows = conn.execute("SELECT * FROM current_month_records").fetchall()
    assert len(rows) == 1
    assert rows[0]["quantity"] == 20   # 第二次上傳的值


def test_import_current_month_does_not_affect_other_months():
    """只取代 SHPB 涵蓋的月份，其他月份不受影響。"""
    db = _make_db()
    df_april = pd.DataFrame([_shpb_row(**{SHPB_COLUMNS["order_date"]: "20260423"})])
    import_current_month(db, df_april)

    df_may = pd.DataFrame([_shpb_row(**{SHPB_COLUMNS["order_date"]: "20260505"})])
    import_current_month(db, df_may)

    with db.get_connection() as conn:
        rows = conn.execute(
            "SELECT order_date FROM current_month_records ORDER BY order_date"
        ).fetchall()
    dates = [r["order_date"][:7] for r in rows]
    assert "2026-04" in dates
    assert "2026-05" in dates


# ---------------------------------------------------------------------------
# _clear_covered_current_month_records (via sync_excel_to_db path)
# ---------------------------------------------------------------------------

def test_sync_clears_current_month_records_for_covered_months():
    """業績明細已涵蓋的月份，sync 後 current_month_records 應被清除。"""
    from src.backend.etl import _clear_covered_current_month_records

    db = _make_db()

    # 寫入 5 月的 SHPB 資料
    df_may = pd.DataFrame([_shpb_row(**{SHPB_COLUMNS["order_date"]: "20260505"})])
    import_current_month(db, df_may)

    # 模擬業績明細已更新至 5 月底
    sales_rows = pd.DataFrame([{
        "order_date": pd.Timestamp("2026-05-31"),
        "customer_name": "慈濟台北",
        "product_code": "T5EL1",
    }])
    _clear_covered_current_month_records(db, sales_rows)

    with db.get_connection() as conn:
        remaining = conn.execute("SELECT COUNT(*) FROM current_month_records").fetchone()[0]
    assert remaining == 0


def test_sync_keeps_future_months_in_current_month_records():
    """sync 只清除已涵蓋的月份，未來月份應保留。"""
    from src.backend.etl import _clear_covered_current_month_records

    db = _make_db()

    # 寫入 4 月和 5 月的 SHPB
    rows = [
        _shpb_row(**{SHPB_COLUMNS["order_date"]: "20260423"}),
        _shpb_row(**{SHPB_COLUMNS["order_date"]: "20260505"}),
    ]
    import_current_month(db, pd.DataFrame(rows))

    # 業績明細只到 4 月底
    sales_rows = pd.DataFrame([{
        "order_date": pd.Timestamp("2026-04-30"),
    }])
    _clear_covered_current_month_records(db, sales_rows)

    with db.get_connection() as conn:
        remaining = conn.execute(
            "SELECT order_date FROM current_month_records"
        ).fetchall()
    months = {r["order_date"][:7] for r in remaining}
    assert "2026-04" not in months   # 已清除
    assert "2026-05" in months       # 保留


# ---------------------------------------------------------------------------
# load_sales_detail with db (merge logic)
# ---------------------------------------------------------------------------

def test_load_sales_detail_merges_current_month_when_db_provided(tmp_path):
    """傳入 db 時，load_sales_detail 應合併 current_month_records 的資料。"""
    from src.backend.data_loader import load_sales_detail
    from src.backend.forecast_config import ForecastConfig

    # 建立只有歷史資料的假 Excel
    hist_df = pd.DataFrame([{
        "年": 2026, "月": 3, "日": 10,
        "客戶簡稱": "A客戶", "商品號": "P1", "商品簡稱": "商品A",
        "銷+贈S量": 10, "單價NT(淨)": 100, "含稅總額(淨)": 1000,
    }])
    excel_path = tmp_path / "業績明細test.xlsx"
    with pd.ExcelWriter(excel_path) as writer:
        hist_df.to_excel(writer, sheet_name="業績明細", index=False)

    config = ForecastConfig(detail_file="業績明細test.xlsx")
    db = _make_db()

    # 寫入 5 月的當月資料
    df_may = pd.DataFrame([_shpb_row(**{SHPB_COLUMNS["order_date"]: "20260505"})])
    import_current_month(db, df_may)

    result = load_sales_detail(tmp_path, config, db)

    months = set(result["月"].astype(int).tolist())
    assert 3 in months   # 歷史
    assert 5 in months   # 當月 SHPB


def test_load_sales_detail_without_db_returns_only_excel(tmp_path):
    """不傳 db 時行為與原本相同（向後相容）。"""
    from src.backend.data_loader import load_sales_detail
    from src.backend.forecast_config import ForecastConfig

    hist_df = pd.DataFrame([{
        "年": 2026, "月": 3, "日": 10,
        "客戶簡稱": "A客戶", "商品號": "P1", "商品簡稱": "商品A",
        "銷+贈S量": 10, "單價NT(淨)": 100, "含稅總額(淨)": 1000,
    }])
    excel_path = tmp_path / "業績明細test.xlsx"
    with pd.ExcelWriter(excel_path) as writer:
        hist_df.to_excel(writer, sheet_name="業績明細", index=False)

    config = ForecastConfig(detail_file="業績明細test.xlsx")
    result = load_sales_detail(tmp_path, config)   # 沒有 db

    assert list(result["月"].astype(int)) == [3]
