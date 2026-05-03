import pandas as pd
import sqlite3
import json
from pathlib import Path
from src.backend.database import MORDatabase
from src.backend.data_loader import normalize_product_code

def sync_excel_to_db(db: MORDatabase, project_root: Path, config_file: str = "excluded_items.json"):
    # 1. Sync Sales Detail
    sales_file = project_root / "業績明細202401-20260430-George.xlsx"
    if sales_file.exists():
        df_sales = pd.read_excel(sales_file, sheet_name="業績明細")
        # Preprocessing similar to data_loader.py
        df_sales["order_date"] = pd.to_datetime({
            "year": pd.to_numeric(df_sales["年"], errors="coerce"),
            "month": pd.to_numeric(df_sales["月"], errors="coerce"),
            "day": pd.to_numeric(df_sales["日"], errors="coerce")
        }, errors="coerce")
        df_sales = df_sales.dropna(subset=["order_date", "客戶簡稱", "商品號"])
        
        # Prepare for SQL
        to_db = df_sales[[
            "order_date", "客戶簡稱", "商品號", "商品簡稱", "銷+贈S量", "單價NT(淨)"
        ]].copy()
        to_db.columns = ["order_date", "customer_name", "product_code", "product_name", "quantity", "unit_price"]
        to_db["product_code"] = to_db["product_code"].map(normalize_product_code)
        
        with db.get_connection() as conn:
            conn.execute("DELETE FROM sales_records")
            to_db.to_sql("sales_records", conn, if_exists="append", index=False)
            print(f"Synced {len(to_db)} sales records.")

    # 2. Sync Exclusions from JSON (Migration)
    json_path = project_root / config_file
    if json_path.exists():
        with open(json_path, "r", encoding="utf-8") as f:
            excluded_ids = json.load(f)
        with db.get_connection() as conn:
            for pid in excluded_ids:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO item_configs
                    (product_code, is_excluded, is_budgeted, is_visible, status_label, custom_category)
                    VALUES (?, 0, 1, 1, NULL, NULL)
                    """,
                    (normalize_product_code(pid),)
                )
                conn.execute(
                    "UPDATE item_configs SET is_excluded = 1 WHERE product_code = ?",
                    (normalize_product_code(pid),)
                )
            print(f"Migrated {len(excluded_ids)} exclusions from JSON.")

    # 3. Sync Budgets (2026預算報表)
    budget_file = project_root / "2026預算報表-George-20260430.xlsx"
    if budget_file.exists():
        try:
            xl = pd.ExcelFile(budget_file)
            # Find the sheet starting with '07' or containing '預算'
            target_sheet = next((s for s in xl.sheet_names if "07" in s and "預算" in s), xl.sheet_names[0])
            print(f"Loading budget from sheet: {target_sheet}")

            df_budget = pd.read_excel(budget_file, sheet_name=target_sheet)
            # Identify month columns (1-12)
            month_cols = [c for c in df_budget.columns if isinstance(c, int) and 1 <= c <= 12]

            if not month_cols:
                # Try to see if they are strings like "1月"
                month_cols = [c for c in df_budget.columns if any(str(m) in str(c) for m in range(1, 13))]

            if not month_cols:
                print("Warning: No month columns found in budget sheet.")
                return

            # Melt/Unpivot
            melted = df_budget.melt(
                id_vars=["客戶簡稱", "商品號"],
                value_vars=month_cols,
                var_name="month",
                value_name="target_quantity"
            )
            melted["year"] = 2026 # Hardcoded for this specific file, or extract from name
            melted = melted.rename(columns={"客戶簡稱": "customer_name", "商品號": "product_code"})
            melted["product_code"] = melted["product_code"].map(normalize_product_code)

            # Aggregate duplicates to avoid IntegrityError
            melted = melted.groupby(["year", "month", "customer_name", "product_code"], as_index=False)["target_quantity"].sum()
            melted = melted.dropna(subset=["target_quantity"])

            with db.get_connection() as conn:
                conn.execute("DELETE FROM budget_targets WHERE year = 2026")
                melted[["year", "month", "customer_name", "product_code", "target_quantity"]].to_sql(
                    "budget_targets", conn, if_exists="append", index=False
                )
                print(f"Synced budget for 2026.")
        except Exception as e:
            print(f"Error syncing budgets: {e}")

if __name__ == "__main__":
    # Quick test run
    root = Path(__file__).resolve().parents[2]
    db = MORDatabase(root / "mor_workbench.db")
    sync_excel_to_db(db, root)
