"""Product-level monthly review summary."""
from __future__ import annotations

from dataclasses import dataclass

from src.backend.database import MORDatabase
from src.backend.monthly_review_data import MonthlyReviewDataReader


PRODUCT_TOP_N = 20


@dataclass(frozen=True)
class ProductSummaryRow:
    product_code: str
    product_name: str
    actual_quantity: float
    actual_amount: float
    last_year_amount: float
    yoy_growth: float | None
    revenue_share: float
    rank: int
    last_year_rank: int | None


@dataclass(frozen=True)
class ProductSummary:
    rows: list[ProductSummaryRow]


def build_product_summary(db: MORDatabase, year: int, month: int) -> ProductSummary:
    reader = MonthlyReviewDataReader(db)
    cur_amt, cur_qty, names = reader.product_totals(year, month)
    ly_amt, _, ly_names = reader.product_totals(year - 1, month)
    names.update({key: value for key, value in ly_names.items() if key not in names})

    ranks_now = _rank(cur_amt)
    ranks_ly = _rank(ly_amt)
    total = sum(cur_amt.values()) or 1.0

    ordered = sorted(cur_amt.items(), key=lambda kv: -kv[1])[:PRODUCT_TOP_N]

    rows = []
    for product, amount in ordered:
        last_year_amount = ly_amt.get(product, 0.0)
        rows.append(ProductSummaryRow(
            product_code=product,
            product_name=names.get(product, ""),
            actual_quantity=cur_qty.get(product, 0.0),
            actual_amount=amount,
            last_year_amount=last_year_amount,
            yoy_growth=(amount / last_year_amount) if last_year_amount > 0 else None,
            revenue_share=amount / total,
            rank=ranks_now[product],
            last_year_rank=ranks_ly.get(product),
        ))
    return ProductSummary(rows=rows)


def _rank(amounts: dict[str, float]) -> dict[str, int]:
    ordered = sorted(
        (item for item in amounts.items() if item[1] > 0),
        key=lambda kv: -kv[1],
    )
    return {code: idx + 1 for idx, (code, _) in enumerate(ordered)}
