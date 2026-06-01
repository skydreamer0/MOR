"""12-month trend series for the monthly review chart.

For each of the last N months (default 12) ending at the reviewed month,
build a point with:
  actual    — 含稅淨額 from daily_sales_actuals (closed) or sales_records
  forecast  — derived (forecast_qty × period 含稅單價) — same convention as
              monthly_review.review_forecast_amount
  budget    — SUM(budget_targets.target_amount)

Empty months yield zero amounts; the UI may render them as dashed/grey.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from src.backend.database import MORDatabase


TREND_MONTHS = 12


@dataclass(frozen=True)
class TrendPoint:
    year: int
    month: int
    label: str                       # e.g. "26/05"
    actual: float
    forecast: float
    budget: float


@dataclass(frozen=True)
class TrendSeries:
    points: list[TrendPoint]         # oldest first
    previous_year_points: list[TrendPoint] = field(default_factory=list)


def build_trend(
    db: MORDatabase, year: int, month: int, months: int = TREND_MONTHS,
) -> TrendSeries:
    target_months = _last_n_months(year, month, months)
    points = [_build_point(db, y, m) for y, m in target_months]
    previous_year_points = [_build_point(db, y - 1, m) for y, m in target_months]
    return TrendSeries(points=points, previous_year_points=previous_year_points)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _last_n_months(year: int, month: int, n: int) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    y, m = year, month
    for _ in range(n):
        out.append((y, m))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return list(reversed(out))


def _build_point(db: MORDatabase, year: int, month: int) -> TrendPoint:
    actual   = _actual_amount(db, year, month)
    forecast = _forecast_amount(db, year, month)
    budget   = _budget_amount(db, year, month)
    return TrendPoint(
        year=year, month=month,
        label=f"{year % 100:02d}/{month:02d}",
        actual=actual, forecast=forecast, budget=budget,
    )


def _actual_amount(db: MORDatabase, year: int, month: int) -> float:
    with db.get_connection() as conn:
        closed = conn.execute(
            "SELECT id FROM month_close_records WHERE year = ? AND month = ?",
            (year, month),
        ).fetchone()
        if closed:
            r = conn.execute(
                """SELECT SUM(taxed_amount) AS amt FROM daily_sales_actuals
                WHERE sales_year = ? AND sales_month = ?""",
                (year, month),
            ).fetchone()
        else:
            r = conn.execute(
                """SELECT SUM(amount) AS amt FROM sales_records
                WHERE strftime('%Y', order_date) = ? AND strftime('%m', order_date) = ?""",
                (str(year), f"{month:02d}"),
            ).fetchone()
    return float(r["amt"] or 0) if r else 0.0


def _budget_amount(db: MORDatabase, year: int, month: int) -> float:
    with db.get_connection() as conn:
        r = conn.execute(
            "SELECT SUM(target_amount) AS amt FROM budget_targets WHERE year = ? AND month = ?",
            (year, month),
        ).fetchone()
    return float(r["amt"] or 0) if r else 0.0


def _forecast_amount(db: MORDatabase, year: int, month: int) -> float:
    """forecast_qty × 該月平均含稅單價, summed over snapshot rows.

    Mirrors monthly_review.review_forecast_amount semantics; returns 0 when
    snapshot or actuals are missing.
    """
    with db.get_connection() as conn:
        snap = conn.execute(
            """SELECT final_snapshot_id FROM month_close_records
            WHERE year = ? AND month = ?""",
            (year, month),
        ).fetchone()
        if not snap or snap["final_snapshot_id"] is None:
            return 0.0
        sid = snap["final_snapshot_id"]
        fcst_rows = conn.execute(
            """SELECT customer_name, product_code, final_forecast
            FROM snapshot_items WHERE snapshot_id = ?""",
            (sid,),
        ).fetchall()
        price_rows = conn.execute(
            """SELECT customer_name, product_code,
                      SUM(actual_quantity) AS qty,
                      SUM(taxed_amount)    AS amt
            FROM daily_sales_actuals
            WHERE sales_year = ? AND sales_month = ?
            GROUP BY customer_name, product_code""",
            (year, month),
        ).fetchall()
        price_quantity_rows = conn.execute(
            """SELECT product_code, price_quantity
            FROM item_configs
            WHERE price_quantity > 0"""
        ).fetchall()
    price_quantities = {
        r["product_code"]: float(r["price_quantity"] or 0)
        for r in price_quantity_rows
        if r["product_code"]
    }
    price = {
        (r["customer_name"], r["product_code"]):
            (
                float(r["amt"] or 0)
                / (float(r["qty"]) * _quantity_multiplier(r["product_code"], price_quantities))
            ) if r["qty"] else 0.0
        for r in price_rows
    }
    total = 0.0
    for r in fcst_rows:
        qty = float(r["final_forecast"] or 0)
        p   = price.get((r["customer_name"], r["product_code"]), 0.0)
        if qty > 0 and p > 0:
            total += qty * p
    return total


def _quantity_multiplier(product_code: str, price_quantities: dict[str, float]) -> float:
    multiplier = price_quantities.get(product_code, 0.0)
    return multiplier if multiplier > 0 else 1.0
