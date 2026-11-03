"""Compatibility entrypoints for the shared, atomic workbook import pipeline.

Sync discovers dated historical detail, monthly history and budgets by content.
SHPB adapters retain their explicit current/monitor operation intent. Default
writes preserve unrelated facts; daily month replacement requires declared
complete coverage. All retirement, fact and provenance writes share one
transaction in import_service. Source workbooks are never modified.
"""
from pathlib import Path

import pandas as pd

from src.backend.database import MORDatabase


SALES_FILE_PATTERN = "業績明細*.xlsx"
SALES_SHEET_NAME = "業績明細"
SALES_COLUMNS = {
    "year": "年",
    "month": "月",
    "day": "日",
    "customer_name": "客戶簡稱",
    "product_code": "商品號",
    "product_name": "商品簡稱",
    "quantity": "銷+贈S量",
    "unit_price": "單價NT(淨)",
    "amount": "含稅總額(淨)",
}

BUDGET_FILE_PATTERN = "*預算報表*.xlsx"
BUDGET_COLUMNS = {
    "year": "年",
    "customer_name": "客戶簡稱",
    "product_code": "商品號",
    "title": "標  題",
}
BUDGET_TITLE_TO_METRIC = {
    "02預算總量": "base_target_quantity",
    "04預算總額": "target_amount",
    "07預算S總量": "target_quantity",
}
BUDGET_METRICS = ("target_quantity", "target_amount", "base_target_quantity")

# SHPB 出貨報表欄位對應（來源欄名 → 標準欄名）
SHPB_COLUMNS = {
    "order_date":    "出貨日期",   # YYYYMMDD 字串，需轉換
    "customer_name": "客戶簡稱",
    "product_code":  "產品",
    "product_name":  "產品簡稱",
    "sales_qty":     "銷售數量",   # 與贈品數量合計後為 quantity
    "gift_qty":      "贈品數量",
    "unit_price":    "銷貨淨價",
    "amount":        "含稅淨額",
}


def normalize_shpb_records(df_shpb: pd.DataFrame) -> pd.DataFrame:
    from src.backend.import_normalization import normalize_detail
    return normalize_detail(df_shpb, shpb=True)


def import_current_month(db: MORDatabase, df_shpb: pd.DataFrame, *, complete_months=None) -> int:
    """Compatibility DataFrame adapter; changed overlapping snapshots need explicit coverage."""
    from src.backend.import_parser import ParsedTable
    from src.backend.import_service import plan_tables, commit_plan
    plan = plan_tables([ParsedTable('shpb', df_shpb, '<dataframe>', '', '<dataframe>', 1, 1)],
                       intent='current', complete_months=complete_months)
    commit_plan(db, plan)
    return len(plan.frames['current'])


def import_current_workbooks(db, files, *, complete_months=None, daily_partitions=False):
    from src.backend.import_service import preflight, commit_plan
    plan = preflight(files, intent='current', complete_months=complete_months, daily_partitions=daily_partitions)
    return commit_plan(db, plan)


def sync_excel_to_db(db: MORDatabase, project_root: Path, *, default_budget_year=None,
                     complete_months=None, observed_months=None, daily_partitions=False,
                     deduplicate_monthly=False, preview=False, files=None):
    """Discover all selected workbooks; preflight the package before an atomic commit.

    Filenames never select a year or override workbook content. Missing input is
    an error. Daily replacements require explicit complete month coverage.
    """
    from src.backend.import_service import preflight, commit_plan, preview_plan
    if files is None:
        files = [(path.name, path.read_bytes()) for path in sorted(project_root.glob('*.xlsx'))
                 if not path.name.startswith('~$')]
    plan = preflight(files, intent='sync', default_budget_year=default_budget_year,
                     complete_months=complete_months, observed_months=observed_months,
                     daily_partitions=daily_partitions, deduplicate_monthly=deduplicate_monthly, allow_unresolved=preview)
    return preview_plan(db, plan) if preview else commit_plan(db, plan)


def normalize_sales_records(df_sales: pd.DataFrame) -> pd.DataFrame:
    from src.backend.import_normalization import normalize_detail
    return normalize_detail(df_sales)


def normalize_budget_targets(df_budget: pd.DataFrame, default_year: int | None = None) -> pd.DataFrame:
    from src.backend.import_normalization import budget_rows
    return budget_rows(df_budget, default_year)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    db = MORDatabase(root / "mor_workbench.db")
    sync_excel_to_db(db, root)
