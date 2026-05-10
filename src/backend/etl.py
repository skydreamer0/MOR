import json
from pathlib import Path

import pandas as pd

from src.backend.data_loader import normalize_product_code
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

BUDGET_FILE_PATTERN = "2026預算報表*.xlsx"
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


def sync_excel_to_db(db: MORDatabase, project_root: Path, config_file: str = "excluded_items.json"):
    sales_file = _find_first_file(project_root, SALES_FILE_PATTERN)
    if sales_file:
        sales_rows = normalize_sales_records(pd.read_excel(sales_file, sheet_name=SALES_SHEET_NAME))
        with db.get_connection() as conn:
            conn.execute("DELETE FROM sales_records")
            sales_rows.to_sql("sales_records", conn, if_exists="append", index=False)
            print(f"Synced {len(sales_rows)} sales records.")

    json_path = project_root / config_file
    if json_path.exists():
        with open(json_path, "r", encoding="utf-8") as f:
            excluded_ids = json.load(f)
        with db.get_connection() as conn:
            for pid in excluded_ids:
                product_code = normalize_product_code(pid)
                conn.execute(
                    """
                    INSERT OR IGNORE INTO item_configs
                    (product_code, is_excluded, is_budgeted, is_visible, price_quantity, item_status, status_label, custom_category)
                    VALUES (?, 0, 1, 1, 0, 'active', NULL, NULL)
                    """,
                    (product_code,),
                )
                conn.execute(
                    "UPDATE item_configs SET is_excluded = 1 WHERE product_code = ?",
                    (product_code,),
                )
            print(f"Migrated {len(excluded_ids)} exclusions from JSON.")

    budget_file = _find_first_file(project_root, BUDGET_FILE_PATTERN)
    if budget_file:
        try:
            xl = pd.ExcelFile(budget_file)
            target_sheet = xl.sheet_names[0]
            df_budget = pd.read_excel(budget_file, sheet_name=target_sheet)
            budget_rows = normalize_budget_targets(df_budget, default_year=2026)

            with db.get_connection() as conn:
                conn.execute("DELETE FROM budget_targets WHERE year = 2026")
                budget_rows[
                    [
                        "year",
                        "month",
                        "customer_name",
                        "product_code",
                        "target_quantity",
                        "target_amount",
                        "base_target_quantity",
                    ]
                ].to_sql("budget_targets", conn, if_exists="append", index=False)
                print("Synced budget for 2026.")
        except Exception as e:
            print(f"Error syncing budgets: {e}")


def normalize_sales_records(df_sales: pd.DataFrame) -> pd.DataFrame:
    _require_columns(df_sales, SALES_COLUMNS.values())
    order_date = pd.to_datetime(
        {
            "year": pd.to_numeric(df_sales[SALES_COLUMNS["year"]], errors="coerce"),
            "month": pd.to_numeric(df_sales[SALES_COLUMNS["month"]], errors="coerce"),
            "day": pd.to_numeric(df_sales[SALES_COLUMNS["day"]], errors="coerce"),
        },
        errors="coerce",
    )
    normalized = pd.DataFrame(
        {
            "order_date": order_date,
            "customer_name": df_sales[SALES_COLUMNS["customer_name"]],
            "product_code": df_sales[SALES_COLUMNS["product_code"]].map(normalize_product_code),
            "product_name": df_sales[SALES_COLUMNS["product_name"]],
            "quantity": pd.to_numeric(df_sales[SALES_COLUMNS["quantity"]], errors="coerce").fillna(0),
            "unit_price": pd.to_numeric(df_sales[SALES_COLUMNS["unit_price"]], errors="coerce").fillna(0),
            "amount": pd.to_numeric(df_sales[SALES_COLUMNS["amount"]], errors="coerce").fillna(0),
        }
    )
    return normalized.dropna(subset=["order_date", "customer_name", "product_code"])


def normalize_budget_targets(df_budget: pd.DataFrame, default_year: int) -> pd.DataFrame:
    _require_columns(df_budget, BUDGET_COLUMNS.values())
    month_cols = _month_columns(df_budget.columns)
    if not month_cols:
        raise ValueError("No month columns found in budget sheet.")

    id_vars = [
        BUDGET_COLUMNS["customer_name"],
        BUDGET_COLUMNS["product_code"],
        BUDGET_COLUMNS["title"],
    ]
    if BUDGET_COLUMNS["year"] in df_budget.columns:
        id_vars.append(BUDGET_COLUMNS["year"])

    filtered = df_budget[df_budget[BUDGET_COLUMNS["title"]].isin(BUDGET_TITLE_TO_METRIC)].copy()
    melted = filtered.melt(
        id_vars=id_vars,
        value_vars=month_cols,
        var_name="month",
        value_name="value",
    )
    melted["metric"] = melted[BUDGET_COLUMNS["title"]].map(BUDGET_TITLE_TO_METRIC)
    melted["value"] = pd.to_numeric(melted["value"], errors="coerce").fillna(0)
    melted["year"] = (
        pd.to_numeric(melted[BUDGET_COLUMNS["year"]], errors="coerce").fillna(default_year).astype(int)
        if BUDGET_COLUMNS["year"] in melted.columns
        else default_year
    )
    melted["month"] = melted["month"].map(_coerce_month).astype(int)
    melted["customer_name"] = melted[BUDGET_COLUMNS["customer_name"]]
    melted["product_code"] = melted[BUDGET_COLUMNS["product_code"]].map(normalize_product_code)

    pivoted = (
        melted.pivot_table(
            index=["year", "month", "customer_name", "product_code"],
            columns="metric",
            values="value",
            aggfunc="sum",
            fill_value=0,
        )
        .reset_index()
        .rename_axis(None, axis=1)
    )
    for metric in BUDGET_METRICS:
        if metric not in pivoted.columns:
            pivoted[metric] = 0.0

    return pivoted[
        [
            "year",
            "month",
            "customer_name",
            "product_code",
            "target_quantity",
            "target_amount",
            "base_target_quantity",
        ]
    ].dropna(subset=["customer_name", "product_code"])


def _find_first_file(project_root: Path, pattern: str) -> "Path | None":
    matches = sorted(project_root.glob(pattern))
    return matches[0] if matches else None


def _require_columns(df: pd.DataFrame, columns) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {', '.join(missing)}")


def _month_columns(columns) -> list:
    return [column for column in columns if _coerce_month(column) is not None]


def _coerce_month(value) -> "int | None":
    try:
        month = int(value)
    except (TypeError, ValueError):
        return None
    return month if 1 <= month <= 12 else None


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    db = MORDatabase(root / "mor_workbench.db")
    sync_excel_to_db(db, root)
