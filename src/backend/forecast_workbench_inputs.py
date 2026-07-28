from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.backend.daily_sales_importer import fetch_daily_actuals_by_row_id
from src.backend.data_loader import load_sales_detail_from_db, normalize_product_code
from src.backend.forecast_models import ForecastTarget
from src.backend.row_identity import make_row_id


@dataclass(frozen=True)
class BudgetTarget:
    target_quantity: float
    target_amount: float
    base_target_quantity: float = 0.0


@dataclass(frozen=True)
class ForecastRowMonthInput:
    manual_adjustment: float | None
    adjustment_reason: str | None
    current_budget: BudgetTarget
    budget_monthly: list[float]
    budget_monthly_amount: list[float]
    price_quantity: float
    item_status: str
    is_budgeted: bool
    is_visible: bool


@dataclass
class ForecastWorkbenchInputs:
    """Raw DB inputs needed before forecast computation."""

    data: pd.DataFrame
    item_configs: dict[str, dict]
    excluded_item_ids: frozenset[str]
    manual_adjustments: dict[str, float]
    adjustment_reasons: dict[str, str]
    budget_targets: dict[str, BudgetTarget]
    budget_year_map: dict[str, list[float]]
    budget_year_amount_map: dict[str, list[float]]
    budget_months: list[tuple[int, int]]
    daily_actuals: dict

    def row_month_input(self, row_id: str, product_code: str) -> ForecastRowMonthInput:
        item_config = self.item_configs.get(product_code, {})
        is_budgeted = bool(item_config.get("is_budgeted", True))
        current_budget = self.budget_targets.get(row_id, BudgetTarget(0.0, 0.0))
        budget_monthly = self.budget_year_map.get(row_id, [0.0] * 12)
        budget_monthly_amount = self.budget_year_amount_map.get(row_id, [0.0] * 12)

        if not is_budgeted:
            current_budget = BudgetTarget(0.0, 0.0)
            budget_monthly = [0.0] * 12
            budget_monthly_amount = [0.0] * 12

        return ForecastRowMonthInput(
            manual_adjustment=self.manual_adjustments.get(row_id),
            adjustment_reason=self.adjustment_reasons.get(row_id),
            current_budget=current_budget,
            budget_monthly=list(budget_monthly),
            budget_monthly_amount=list(budget_monthly_amount),
            price_quantity=float(item_config.get("price_quantity") or 0),
            item_status=str(item_config.get("item_status") or "active"),
            is_budgeted=is_budgeted,
            is_visible=self.visible_product(product_code),
        )

    def visible_product(self, product_code: str) -> bool:
        return bool(self.item_configs.get(product_code, {}).get("is_visible", True))

    @property
    def forecast_excluded_product_ids(self) -> frozenset[str]:
        return self.excluded_item_ids

    @property
    def company_budgets(self) -> list[BudgetTarget]:
        return list(self.budget_targets.values())

    @property
    def available_budget_months(self) -> list[tuple[int, int]]:
        return list(self.budget_months)


def load_forecast_workbench_inputs(db, target: ForecastTarget) -> ForecastWorkbenchInputs:
    data = load_sales_detail_from_db(db)
    item_configs = load_item_configs(db)
    excluded_item_ids = frozenset(pid for pid, cfg in item_configs.items() if cfg["is_excluded"])
    manual_adjustments, adjustment_reasons = load_adjustments(db, target.year, target.month)
    return ForecastWorkbenchInputs(
        data=data,
        item_configs=item_configs,
        excluded_item_ids=excluded_item_ids,
        manual_adjustments=manual_adjustments,
        adjustment_reasons=adjustment_reasons,
        budget_targets=load_budgets(db, target.year, target.month),
        budget_year_map=load_budget_year(db, target.year),
        budget_year_amount_map=load_budget_year_amounts(db, target.year),
        budget_months=list_budget_months(db),
        daily_actuals=fetch_daily_actuals_by_row_id(db, target.year, target.month),
    )


def build_items_from_sales_data(data: pd.DataFrame, db) -> list[dict]:
    product_code_column = "\u5546\u54c1\u865f"
    product_name_column = "\u5546\u54c1\u7c21\u7a31"
    products = data[[product_code_column, product_name_column]].copy()
    products[product_code_column] = products[product_code_column].map(normalize_product_code)
    unique_products = products.drop_duplicates(product_code_column)
    item_configs = load_item_configs(db)
    items = []
    for _, row in unique_products.iterrows():
        product_code = row[product_code_column]
        config = item_configs.get(
            product_code,
            {
                "is_excluded": False,
                "is_budgeted": True,
                "is_visible": True,
                "price_quantity": 0.0,
                "item_status": "active",
            },
        )
        items.append(
            {
                "product_code": product_code,
                "product_name": row[product_name_column],
                **config,
            }
        )
    return items


def load_item_configs(db) -> dict[str, dict]:
    with db.get_connection() as conn:
        rows = conn.execute("SELECT * FROM item_configs").fetchall()
    configs: dict[str, dict] = {}
    for row in rows:
        entry = {
            "is_excluded": bool(row["is_excluded"]),
            "is_budgeted": bool(row["is_budgeted"]),
            "is_visible": bool(row["is_visible"]),
            "price_quantity": float(row["price_quantity"] or 0),
            "item_status": _normalize_item_status(row["item_status"], row["status_label"]),
        }
        configs[row["product_code"]] = entry
        configs.setdefault(normalize_product_code(row["product_code"]), entry)
    return configs


def load_adjustments(db, year: int, month: int) -> tuple[dict[str, float], dict[str, str]]:
    manual_adjustments = {}
    adjustment_reasons = {}
    with db.get_connection() as conn:
        rows = conn.execute(
            """
            SELECT customer_name, product_code, manual_quantity, adjustment_reason
            FROM forecast_adjustments
            WHERE year = ? AND month = ?
            """,
            (year, month),
        ).fetchall()
    for row in rows:
        row_id = make_row_id(row["customer_name"], row["product_code"])
        if row["manual_quantity"] is not None:
            manual_adjustments[row_id] = row["manual_quantity"]
        if row["adjustment_reason"]:
            adjustment_reasons[row_id] = row["adjustment_reason"]
    return manual_adjustments, adjustment_reasons


def load_budgets(db, year: int, month: int) -> dict[str, BudgetTarget]:
    budgets = {}
    with db.get_connection() as conn:
        rows = conn.execute(
            """
            SELECT customer_name, product_code, target_quantity, target_amount, base_target_quantity
            FROM budget_targets
            WHERE year = ? AND month = ?
            """,
            (year, month),
        ).fetchall()
    for row in rows:
        row_id = make_row_id(row["customer_name"], row["product_code"])
        budgets[row_id] = BudgetTarget(
            target_quantity=float(row["target_quantity"] or 0),
            target_amount=float(row["target_amount"] or 0),
            base_target_quantity=float(row["base_target_quantity"] or 0),
        )
    return budgets


def load_budget_year(db, year: int) -> dict[str, list[float]]:
    """Return a 12-element monthly quantity array per row_id for the given year."""
    with db.get_connection() as conn:
        rows = conn.execute(
            """
            SELECT customer_name, product_code, month, target_quantity
            FROM budget_targets
            WHERE year = ?
            """,
            (year,),
        ).fetchall()
    result: dict[str, list[float]] = {}
    for row in rows:
        row_id = make_row_id(row["customer_name"], row["product_code"])
        if row_id not in result:
            result[row_id] = [0.0] * 12
        m = int(row["month"]) - 1
        if 0 <= m < 12:
            result[row_id][m] = float(row["target_quantity"] or 0)
    return result


def load_budget_year_amounts(db, year: int) -> dict[str, list[float]]:
    """Return a 12-element monthly amount array per row_id for the given year."""
    with db.get_connection() as conn:
        rows = conn.execute(
            """
            SELECT customer_name, product_code, month, target_amount
            FROM budget_targets
            WHERE year = ?
            """,
            (year,),
        ).fetchall()
    result: dict[str, list[float]] = {}
    for row in rows:
        row_id = make_row_id(row["customer_name"], row["product_code"])
        if row_id not in result:
            result[row_id] = [0.0] * 12
        m = int(row["month"]) - 1
        if 0 <= m < 12:
            result[row_id][m] = float(row["target_amount"] or 0)
    return result


def list_budget_months(db) -> list[tuple[int, int]]:
    with db.get_connection() as conn:
        rows = conn.execute(
            """
            SELECT year, month
            FROM budget_targets
            GROUP BY year, month
            ORDER BY year, month
            """
        ).fetchall()
    return [(int(row["year"]), int(row["month"])) for row in rows]


def _normalize_item_status(item_status: object, legacy_status_label: object = "") -> str:
    if str(item_status or "").strip() == "discontinued":
        return "discontinued"
    if str(legacy_status_label or "").strip() == "停用":
        return "discontinued"
    return "active"
