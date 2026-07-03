"""Customer-level monthly review summary."""
from __future__ import annotations

from dataclasses import dataclass

from src.backend.database import MORDatabase
from src.backend.monthly_review_data import MonthlyReviewDataReader


CUSTOMER_TOP_N = 20


@dataclass(frozen=True)
class CustomerProductRow:
    product_code: str
    product_name: str
    actual_quantity: float
    actual_amount: float
    last_year_amount: float
    yoy_growth: float | None


@dataclass(frozen=True)
class CustomerSummaryRow:
    customer_name: str
    actual_amount: float
    last_year_amount: float
    budget_amount: float
    yoy_growth: float | None
    budget_achievement: float | None
    rank: int
    last_year_rank: int | None
    products: list[CustomerProductRow]


@dataclass(frozen=True)
class CustomerSummary:
    rows: list[CustomerSummaryRow]


def build_customer_summary(db: MORDatabase, year: int, month: int) -> CustomerSummary:
    reader = MonthlyReviewDataReader(db)
    current = reader.customer_amounts(year, month)
    last_year = reader.customer_amounts(year - 1, month)
    budgets = reader.budget_amounts_by_customer(year, month)
    products = _customer_products(reader, year, month)

    ranks_now = _rank(current)
    ranks_ly = _rank(last_year)

    ordered = sorted(current.items(), key=lambda kv: -kv[1])[:CUSTOMER_TOP_N]

    rows = []
    for customer, amount in ordered:
        last_year_amount = last_year.get(customer, 0.0)
        budget_amount = budgets.get(customer, 0.0)
        rows.append(CustomerSummaryRow(
            customer_name=customer,
            actual_amount=amount,
            last_year_amount=last_year_amount,
            budget_amount=budget_amount,
            yoy_growth=(amount / last_year_amount) if last_year_amount > 0 else None,
            budget_achievement=(amount / budget_amount) if budget_amount > 0 else None,
            rank=ranks_now[customer],
            last_year_rank=ranks_ly.get(customer),
            products=products.get(customer, []),
        ))
    return CustomerSummary(rows=rows)


def _customer_products(
    reader: MonthlyReviewDataReader, year: int, month: int,
) -> dict[str, list[CustomerProductRow]]:
    if reader.close_record(year, month) is None:
        return {}

    actuals = reader.actuals_by_row(year, month)
    last_year = reader.last_year_rows(year, month)
    out: dict[str, list[CustomerProductRow]] = {}

    for row_id, actual in actuals.items():
        customer = actual["customer_name"]
        product = actual["product_code"]
        amount = float(actual["amount"] or 0)
        last_year_amount = float(last_year.get(row_id, {}).get("amount", 0.0))
        out.setdefault(customer, []).append(CustomerProductRow(
            product_code=product,
            product_name=actual["product_name"] or "",
            actual_quantity=float(actual["qty"] or 0),
            actual_amount=amount,
            last_year_amount=last_year_amount,
            yoy_growth=(amount / last_year_amount) if last_year_amount > 0 else None,
        ))

    for products in out.values():
        products.sort(key=lambda row: -row.actual_amount)
    return out


def _rank(amounts: dict[str, float]) -> dict[str, int]:
    ordered = sorted(
        (item for item in amounts.items() if item[1] > 0),
        key=lambda kv: -kv[1],
    )
    return {customer: idx + 1 for idx, (customer, _) in enumerate(ordered)}
