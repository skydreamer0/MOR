"""Customer-level monthly review summary.

Builds a ranked customer view for one closed month:
  - Top-N customers by 含稅淨額
  - Rank change vs same month last year (↑ / ↓ / 新進 / 流失)
  - YoY and budget achievement (amount-side)
  - Optional drill-down rows: each customer's per-product detail this month

All amounts are 含稅淨額 (taxed net of discount):
  daily_sales_actuals.taxed_amount  for closed months
  sales_records.amount              for fallback
  budget_targets.target_amount
"""
from __future__ import annotations

from dataclasses import dataclass

from src.backend.database import MORDatabase


CUSTOMER_TOP_N = 20


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CustomerProductRow:
    product_code: str
    product_name: str
    actual_quantity: float
    actual_amount: float
    last_year_amount: float
    yoy_growth: float | None         # actual / last_year


@dataclass(frozen=True)
class CustomerSummaryRow:
    customer_name: str
    actual_amount: float
    last_year_amount: float
    budget_amount: float
    yoy_growth: float | None
    budget_achievement: float | None
    rank: int                        # this month's rank, 1-based
    last_year_rank: int | None       # None == not in last year's ranking
    products: list[CustomerProductRow]


@dataclass(frozen=True)
class CustomerSummary:
    rows: list[CustomerSummaryRow]   # already capped to CUSTOMER_TOP_N


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_customer_summary(db: MORDatabase, year: int, month: int) -> CustomerSummary:
    current   = _customer_totals(db, year, month)
    last_year = _customer_totals(db, year - 1, month)
    budgets   = _customer_budgets(db, year, month)
    products  = _customer_products(db, year, month)

    ranks_now = _rank(current)
    ranks_ly  = _rank(last_year)

    # Sort by current month amount desc; pick top-N.
    ordered = sorted(current.items(), key=lambda kv: -kv[1])[:CUSTOMER_TOP_N]

    rows = []
    for customer, amount in ordered:
        ly_amt    = last_year.get(customer, 0.0)
        budget    = budgets.get(customer, 0.0)
        rows.append(CustomerSummaryRow(
            customer_name=customer,
            actual_amount=amount,
            last_year_amount=ly_amt,
            budget_amount=budget,
            yoy_growth=(amount / ly_amt) if ly_amt > 0 else None,
            budget_achievement=(amount / budget) if budget > 0 else None,
            rank=ranks_now[customer],
            last_year_rank=ranks_ly.get(customer),
            products=products.get(customer, []),
        ))
    return CustomerSummary(rows=rows)


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def _customer_totals(db: MORDatabase, year: int, month: int) -> dict[str, float]:
    with db.get_connection() as conn:
        closed = conn.execute(
            "SELECT id FROM month_close_records WHERE year = ? AND month = ?",
            (year, month),
        ).fetchone()
        if closed:
            rows = conn.execute(
                """SELECT customer_name, SUM(taxed_amount) AS amt
                FROM daily_sales_actuals
                WHERE sales_year = ? AND sales_month = ?
                GROUP BY customer_name""",
                (year, month),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT customer_name, SUM(amount) AS amt
                FROM sales_records
                WHERE strftime('%Y', order_date) = ? AND strftime('%m', order_date) = ?
                GROUP BY customer_name""",
                (str(year), f"{month:02d}"),
            ).fetchall()
    return {r["customer_name"]: float(r["amt"] or 0) for r in rows if r["customer_name"]}


def _customer_budgets(db: MORDatabase, year: int, month: int) -> dict[str, float]:
    with db.get_connection() as conn:
        rows = conn.execute(
            """SELECT customer_name, SUM(target_amount) AS amt
            FROM budget_targets
            WHERE year = ? AND month = ?
            GROUP BY customer_name""",
            (year, month),
        ).fetchall()
    return {r["customer_name"]: float(r["amt"] or 0) for r in rows if r["customer_name"]}


def _customer_products(
    db: MORDatabase, year: int, month: int,
) -> dict[str, list[CustomerProductRow]]:
    """Per-customer product detail for the current month + YoY for the same product/customer."""
    out: dict[str, list[CustomerProductRow]] = {}
    with db.get_connection() as conn:
        closed_now = conn.execute(
            "SELECT id FROM month_close_records WHERE year = ? AND month = ?",
            (year, month),
        ).fetchone()
        if not closed_now:
            return out
        cur_rows = conn.execute(
            """SELECT customer_name, product_code,
                      MAX(product_name)    AS product_name,
                      SUM(actual_quantity) AS qty,
                      SUM(taxed_amount)    AS amt
            FROM daily_sales_actuals
            WHERE sales_year = ? AND sales_month = ?
            GROUP BY customer_name, product_code""",
            (year, month),
        ).fetchall()

        # Last year same month, same (customer, product) — for per-product YoY
        ly_year = year - 1
        closed_ly = conn.execute(
            "SELECT id FROM month_close_records WHERE year = ? AND month = ?",
            (ly_year, month),
        ).fetchone()
        if closed_ly:
            ly_rows = conn.execute(
                """SELECT customer_name, product_code, SUM(taxed_amount) AS amt
                FROM daily_sales_actuals
                WHERE sales_year = ? AND sales_month = ?
                GROUP BY customer_name, product_code""",
                (ly_year, month),
            ).fetchall()
        else:
            ly_rows = conn.execute(
                """SELECT customer_name, product_code, SUM(amount) AS amt
                FROM sales_records
                WHERE strftime('%Y', order_date) = ? AND strftime('%m', order_date) = ?
                GROUP BY customer_name, product_code""",
                (str(ly_year), f"{month:02d}"),
            ).fetchall()
        ly_map = {
            (r["customer_name"], r["product_code"]): float(r["amt"] or 0)
            for r in ly_rows
        }

    for r in cur_rows:
        customer = r["customer_name"]
        product  = r["product_code"]
        amt      = float(r["amt"] or 0)
        ly_amt   = ly_map.get((customer, product), 0.0)
        out.setdefault(customer, []).append(CustomerProductRow(
            product_code=product,
            product_name=r["product_name"] or "",
            actual_quantity=float(r["qty"] or 0),
            actual_amount=amt,
            last_year_amount=ly_amt,
            yoy_growth=(amt / ly_amt) if ly_amt > 0 else None,
        ))

    # Each customer's product list sorted by amount desc
    for products in out.values():
        products.sort(key=lambda p: -p.actual_amount)
    return out


def _rank(amounts: dict[str, float]) -> dict[str, int]:
    """1-based rank by amount desc. Customers with amount == 0 are unranked (omitted)."""
    ordered = sorted(
        (item for item in amounts.items() if item[1] > 0),
        key=lambda kv: -kv[1],
    )
    return {customer: idx + 1 for idx, (customer, _) in enumerate(ordered)}
