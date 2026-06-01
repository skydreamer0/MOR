"""History Service — batch SQL queries for last-month performance and 6-month trends.

Reads from ``sales_records`` and ``budget_targets`` in ``mor_workbench.db``
and returns look-up dicts keyed by canonical forecast row IDs.

All queries use a single DB round-trip per data-set to avoid N+1.
"""
from __future__ import annotations

from dataclasses import dataclass
from src.backend.database import MORDatabase
from src.backend.row_identity import make_row_id


@dataclass(frozen=True)
class LastMonthPerformance:
    """Actual sales quantity and budget target for a single row last month."""
    actual: float
    budget: float

    @property
    def gap(self) -> float:
        return self.actual - self.budget

    @property
    def achievement_rate(self) -> float:
        return (self.actual / self.budget * 100) if self.budget > 0 else 0.0


def _prev_month(year: int, month: int) -> tuple[int, int]:
    """Return (year, month) of the previous month."""
    if month == 1:
        return year - 1, 12
    return year, month - 1


def _past_n_months(year: int, month: int, n: int) -> list[tuple[int, int]]:
    """Return a list of (year, month) tuples for the *n* months before the target, oldest first."""
    result: list[tuple[int, int]] = []
    y, m = year, month
    for _ in range(n):
        y, m = _prev_month(y, m)
        result.append((y, m))
    result.reverse()  # oldest → newest
    return result


def fetch_last_month_actuals(
    db: MORDatabase,
    target_year: int,
    target_month: int,
) -> dict[str, float]:
    """Return {row_id: total_quantity} for the month immediately before the target."""
    prev_y, prev_m = _prev_month(target_year, target_month)
    with db.get_connection() as conn:
        rows = conn.execute("""
            SELECT customer_name, product_code, SUM(quantity) AS total_qty
            FROM sales_records
            WHERE strftime('%Y', order_date) = ?
              AND strftime('%m', order_date) = ?
            GROUP BY customer_name, product_code
        """, (str(prev_y), f"{prev_m:02d}")).fetchall()

    return {
        make_row_id(r["customer_name"], r["product_code"]): float(r["total_qty"] or 0)
        for r in rows
    }


def fetch_last_month_budgets(
    db: MORDatabase,
    target_year: int,
    target_month: int,
) -> dict[str, float]:
    """Return {row_id: target_quantity} for last month's budget targets."""
    prev_y, prev_m = _prev_month(target_year, target_month)
    with db.get_connection() as conn:
        rows = conn.execute("""
            SELECT customer_name, product_code, target_quantity
            FROM budget_targets
            WHERE year = ? AND month = ?
        """, (prev_y, prev_m)).fetchall()

    return {
        make_row_id(r["customer_name"], r["product_code"]): float(r["target_quantity"] or 0)
        for r in rows
    }


def fetch_last_month_performance(
    db: MORDatabase,
    target_year: int,
    target_month: int,
) -> dict[str, LastMonthPerformance]:
    """Merge actuals + budgets into a single look-up for last month."""
    actuals = fetch_last_month_actuals(db, target_year, target_month)
    budgets = fetch_last_month_budgets(db, target_year, target_month)
    all_keys = set(actuals) | set(budgets)
    return {
        key: LastMonthPerformance(
            actual=actuals.get(key, 0.0),
            budget=budgets.get(key, 0.0),
        )
        for key in all_keys
    }


def fetch_trend_6m(
    db: MORDatabase,
    target_year: int,
    target_month: int,
) -> dict[str, list[float]]:
    """Return {row_id: [qty_m-6, qty_m-5, ... qty_m-1]} for the 6 months before target.

    Missing months are filled with 0.0 to guarantee length-6 arrays.
    """
    months = _past_n_months(target_year, target_month, 6)
    # Build a single SQL with OR conditions for each (year, month)
    conditions = " OR ".join(
        f"(strftime('%Y', order_date) = '{y}' AND strftime('%m', order_date) = '{m:02d}')"
        for y, m in months
    )
    with db.get_connection() as conn:
        rows = conn.execute(f"""
            SELECT customer_name, product_code,
                   CAST(strftime('%Y', order_date) AS INTEGER) AS yr,
                   CAST(strftime('%m', order_date) AS INTEGER) AS mo,
                   SUM(quantity) AS total_qty
            FROM sales_records
            WHERE {conditions}
            GROUP BY customer_name, product_code, yr, mo
        """).fetchall()

    # Build nested dict: row_id -> {(y,m): qty}
    raw: dict[str, dict[tuple[int, int], float]] = {}
    for r in rows:
        row_id = make_row_id(r["customer_name"], r["product_code"])
        raw.setdefault(row_id, {})[(int(r['yr']), int(r['mo']))] = float(r['total_qty'] or 0)

    # Flatten to ordered list[float] of length 6
    result: dict[str, list[float]] = {}
    for row_id, month_map in raw.items():
        result[row_id] = [month_map.get(m, 0.0) for m in months]
    return result


def enrich_rows_with_history(
    rows: list,
    db: MORDatabase,
    target_year: int,
    target_month: int,
) -> list:
    """Batch-enrich a list of ForecastRow objects with last-month and trend data.

    Returns a new list with updated rows (ForecastRow is frozen, so we use replace).
    """
    from dataclasses import replace

    perf = fetch_last_month_performance(db, target_year, target_month)
    trends = fetch_trend_6m(db, target_year, target_month)

    enriched = []
    for row in rows:
        p = perf.get(row.row_id)
        t = trends.get(row.row_id)
        # avg_3m from the last 3 entries of trend_6m
        avg_3m = 0.0
        if t:
            last_3 = [v for v in t[-3:] if v > 0]
            avg_3m = sum(last_3) / len(last_3) if last_3 else 0.0

        enriched.append(replace(
            row,
            last_month_actual=p.actual if p else 0.0,
            last_month_budget=p.budget if p else 0.0,
            trend_6m=t if t else [0.0] * 6,
            avg_3m=round(avg_3m, 2),
        ))
    return enriched
