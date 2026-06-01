"""Product-level monthly review summary — Top N by 含稅淨額.

Mirrors monthly_review_customers but aggregates by product. Useful when the
customer view is too granular (the same big product spread across many small
customers) and you want to see which SKUs are actually moving the needle.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.backend.database import MORDatabase


PRODUCT_TOP_N = 20


@dataclass(frozen=True)
class ProductSummaryRow:
    product_code: str
    product_name: str
    actual_quantity: float
    actual_amount: float             # 含稅淨額
    last_year_amount: float
    yoy_growth: float | None
    revenue_share: float             # 0.18 == 18% of this month's total amount
    rank: int
    last_year_rank: int | None


@dataclass(frozen=True)
class ProductSummary:
    rows: list[ProductSummaryRow]


def build_product_summary(db: MORDatabase, year: int, month: int) -> ProductSummary:
    cur_amt, cur_qty, names = _product_totals(db, year, month)
    ly_amt, _, ly_names     = _product_totals(db, year - 1, month)
    names.update({k: v for k, v in ly_names.items() if k not in names})

    ranks_now = _rank(cur_amt)
    ranks_ly  = _rank(ly_amt)
    total     = sum(cur_amt.values()) or 1.0

    ordered = sorted(cur_amt.items(), key=lambda kv: -kv[1])[:PRODUCT_TOP_N]

    rows = []
    for product, amount in ordered:
        ly = ly_amt.get(product, 0.0)
        rows.append(ProductSummaryRow(
            product_code=product,
            product_name=names.get(product, ""),
            actual_quantity=cur_qty.get(product, 0.0),
            actual_amount=amount,
            last_year_amount=ly,
            yoy_growth=(amount / ly) if ly > 0 else None,
            revenue_share=amount / total,
            rank=ranks_now[product],
            last_year_rank=ranks_ly.get(product),
        ))
    return ProductSummary(rows=rows)


def _product_totals(
    db: MORDatabase, year: int, month: int,
) -> tuple[dict[str, float], dict[str, float], dict[str, str]]:
    """Return (amount_by_product, qty_by_product, name_by_product)."""
    amounts: dict[str, float] = {}
    qtys:    dict[str, float] = {}
    names:   dict[str, str]   = {}
    with db.get_connection() as conn:
        closed = conn.execute(
            "SELECT id FROM month_close_records WHERE year = ? AND month = ?",
            (year, month),
        ).fetchone()
        if closed:
            rows = conn.execute(
                """SELECT product_code,
                          MAX(product_name)    AS name,
                          SUM(actual_quantity) AS qty,
                          SUM(taxed_amount)    AS amt
                FROM daily_sales_actuals
                WHERE sales_year = ? AND sales_month = ?
                GROUP BY product_code""",
                (year, month),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT product_code,
                          MAX(product_name) AS name,
                          SUM(quantity)     AS qty,
                          SUM(amount)       AS amt
                FROM sales_records
                WHERE strftime('%Y', order_date) = ? AND strftime('%m', order_date) = ?
                GROUP BY product_code""",
                (str(year), f"{month:02d}"),
            ).fetchall()
    for r in rows:
        code = r["product_code"]
        if not code:
            continue
        amounts[code] = float(r["amt"] or 0)
        qtys[code]    = float(r["qty"] or 0)
        if r["name"]:
            names[code] = r["name"]
    return amounts, qtys, names


def _rank(amounts: dict[str, float]) -> dict[str, int]:
    ordered = sorted(
        (item for item in amounts.items() if item[1] > 0),
        key=lambda kv: -kv[1],
    )
    return {code: idx + 1 for idx, (code, _) in enumerate(ordered)}
