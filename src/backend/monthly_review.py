"""Monthly review service (Phase 7).

All data comes from the DB — no Excel file dependency.

Data sources:
  actual       → daily_sales_actuals   (the closed month's imported records)
  forecast     → snapshot_items        (via month_close_records.final_snapshot_id)
  budget       → budget_targets
  last year    → daily_sales_actuals   if (year-1, month) is closed,
                 else sales_records    (synced from Excel)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from src.backend.database import MORDatabase


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ReviewRow:
    """Per-row comparison: actual vs forecast vs budget vs last year."""
    customer_name: str
    product_code: str
    product_name: str
    actual_quantity: float
    actual_amount: float
    forecast_quantity: float         # from close snapshot
    budget_quantity: float
    last_year_quantity: float        # 0 = no data
    last_year_amount: float
    # Derived
    forecast_gap: float              # actual - forecast
    forecast_accuracy: float | None  # actual / forecast (None if forecast == 0)
    yoy_growth: float | None         # actual / last_year (None if last_year == 0)
    budget_achievement: float | None # actual / budget   (None if budget == 0)


@dataclass(frozen=True)
class MonthlyReviewSummary:
    year: int
    month: int
    closed_at: str
    # Totals
    actual_quantity_total: float
    actual_amount_total: float
    forecast_quantity_total: float
    budget_quantity_total: float
    last_year_quantity_total: float
    last_year_amount_total: float
    # Rates
    forecast_accuracy_total: float | None
    yoy_growth_total: float | None
    budget_achievement_total: float | None
    # Row details
    rows: list[ReviewRow]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_monthly_review(
    db: MORDatabase,
    year: int,
    month: int,
) -> MonthlyReviewSummary:
    """Build a complete monthly review from DB-only data.

    Raises ValueError if the month is not closed.
    """
    close_rec = _get_close_record(db, year, month)
    if close_rec is None:
        raise ValueError(f"{year}/{month:02d} 尚未結月，無法產生月底檢討。")

    actuals    = _load_actuals(db, year, month)
    forecasts  = _load_forecasts(db, close_rec["final_snapshot_id"])
    budgets    = _load_budgets(db, year, month)
    last_year  = _load_last_year(db, year, month)

    rows = _merge_rows(actuals, forecasts, budgets, last_year)
    return _make_summary(year, month, close_rec["closed_at"], rows)


def list_reviewable_months(db: MORDatabase) -> list[tuple[int, int]]:
    """Return all closed months that have a final snapshot, newest first."""
    with db.get_connection() as conn:
        result = conn.execute(
            """
            SELECT year, month
            FROM   month_close_records
            WHERE  final_snapshot_id IS NOT NULL
            ORDER  BY year DESC, month DESC
            """
        ).fetchall()
    return [(r["year"], r["month"]) for r in result]


# ---------------------------------------------------------------------------
# Internal loaders
# ---------------------------------------------------------------------------

def _get_close_record(db: MORDatabase, year: int, month: int) -> dict | None:
    with db.get_connection() as conn:
        row = conn.execute(
            """
            SELECT year, month, closed_at, final_snapshot_id,
                   actual_quantity_total, actual_amount_total
            FROM   month_close_records
            WHERE  year = ? AND month = ?
            """,
            (year, month),
        ).fetchone()
    return dict(row) if row else None


def _load_actuals(db: MORDatabase, year: int, month: int) -> dict[str, dict]:
    """key = customer_name__product_code"""
    with db.get_connection() as conn:
        rows = conn.execute(
            """
            SELECT customer_name, product_code,
                   SUM(actual_quantity) AS qty,
                   SUM(taxed_amount)    AS amount
            FROM   daily_sales_actuals
            WHERE  sales_year = ? AND sales_month = ?
            GROUP  BY customer_name, product_code
            """,
            (year, month),
        ).fetchall()
    return {
        f"{r['customer_name']}__{r['product_code']}": {
            "customer_name": r["customer_name"],
            "product_code": r["product_code"],
            "qty": float(r["qty"] or 0),
            "amount": float(r["amount"] or 0),
        }
        for r in rows
    }


def _load_forecasts(db: MORDatabase, snapshot_id: int | None) -> dict[str, dict]:
    if snapshot_id is None:
        return {}
    with db.get_connection() as conn:
        rows = conn.execute(
            """
            SELECT si.customer_name, si.product_code,
                   si.final_forecast,
                   fs.snapshot_name
            FROM   snapshot_items si
            JOIN   forecast_snapshots fs ON fs.id = si.snapshot_id
            WHERE  si.snapshot_id = ?
            """,
            (snapshot_id,),
        ).fetchall()
    return {
        f"{r['customer_name']}__{r['product_code']}": {
            "final_forecast": float(r["final_forecast"] or 0),
        }
        for r in rows
    }


def _load_budgets(db: MORDatabase, year: int, month: int) -> dict[str, dict]:
    with db.get_connection() as conn:
        rows = conn.execute(
            """
            SELECT customer_name, product_code,
                   target_quantity, target_amount
            FROM   budget_targets
            WHERE  year = ? AND month = ?
            """,
            (year, month),
        ).fetchall()
    return {
        f"{r['customer_name']}__{r['product_code']}": {
            "target_quantity": float(r["target_quantity"] or 0),
            "target_amount": float(r["target_amount"] or 0),
        }
        for r in rows
    }


def _load_last_year(db: MORDatabase, year: int, month: int) -> dict[str, dict]:
    """Prefer daily_sales_actuals for closed last-year months, fallback to sales_records."""
    ly_year = year - 1

    # Check if last year same month is closed
    with db.get_connection() as conn:
        closed = conn.execute(
            "SELECT id FROM month_close_records WHERE year = ? AND month = ?",
            (ly_year, month),
        ).fetchone()

        if closed:
            rows = conn.execute(
                """
                SELECT customer_name, product_code,
                       SUM(actual_quantity) AS qty,
                       SUM(taxed_amount)    AS amount
                FROM   daily_sales_actuals
                WHERE  sales_year = ? AND sales_month = ?
                GROUP  BY customer_name, product_code
                """,
                (ly_year, month),
            ).fetchall()
        else:
            # Fall back to sales_records (synced from Excel)
            rows = conn.execute(
                """
                SELECT customer_name, product_code,
                       SUM(quantity) AS qty,
                       SUM(amount)   AS amount
                FROM   sales_records
                WHERE  strftime('%Y', order_date) = ?
                  AND  strftime('%m', order_date) = ?
                GROUP  BY customer_name, product_code
                """,
                (str(ly_year), f"{month:02d}"),
            ).fetchall()

    return {
        f"{r['customer_name']}__{r['product_code']}": {
            "qty": float(r["qty"] or 0),
            "amount": float(r["amount"] or 0),
        }
        for r in rows
    }


# ---------------------------------------------------------------------------
# Merge and compute
# ---------------------------------------------------------------------------

def _merge_rows(
    actuals: dict[str, dict],
    forecasts: dict[str, dict],
    budgets: dict[str, dict],
    last_year: dict[str, dict],
) -> list[ReviewRow]:
    # Union of all known row_ids (actual is the primary source)
    all_ids = set(actuals) | set(forecasts) | set(budgets)
    rows = []
    for row_id in all_ids:
        a   = actuals.get(row_id, {})
        f   = forecasts.get(row_id, {})
        b   = budgets.get(row_id, {})
        ly  = last_year.get(row_id, {})

        # Parse customer / product from row_id
        parts = row_id.split("__", 1)
        customer = parts[0] if len(parts) == 2 else row_id
        product  = parts[1] if len(parts) == 2 else ""

        act_qty   = a.get("qty", 0.0)
        act_amt   = a.get("amount", 0.0)
        fcst_qty  = f.get("final_forecast", 0.0)
        bud_qty   = b.get("target_quantity", 0.0)
        ly_qty    = ly.get("qty", 0.0)
        ly_amt    = ly.get("amount", 0.0)

        rows.append(ReviewRow(
            customer_name=a.get("customer_name", customer),
            product_code=a.get("product_code", product),
            product_name="",
            actual_quantity=act_qty,
            actual_amount=act_amt,
            forecast_quantity=fcst_qty,
            budget_quantity=bud_qty,
            last_year_quantity=ly_qty,
            last_year_amount=ly_amt,
            forecast_gap=act_qty - fcst_qty,
            forecast_accuracy=(act_qty / fcst_qty) if fcst_qty > 0 else None,
            yoy_growth=(act_qty / ly_qty) if ly_qty > 0 else None,
            budget_achievement=(act_qty / bud_qty) if bud_qty > 0 else None,
        ))

    rows.sort(key=lambda r: (r.customer_name, r.product_code))
    return rows


def _make_summary(
    year: int,
    month: int,
    closed_at: str,
    rows: list[ReviewRow],
) -> MonthlyReviewSummary:
    act_qty_total  = sum(r.actual_quantity   for r in rows)
    act_amt_total  = sum(r.actual_amount     for r in rows)
    fcst_qty_total = sum(r.forecast_quantity for r in rows)
    bud_qty_total  = sum(r.budget_quantity   for r in rows)
    ly_qty_total   = sum(r.last_year_quantity for r in rows)
    ly_amt_total   = sum(r.last_year_amount  for r in rows)

    return MonthlyReviewSummary(
        year=year,
        month=month,
        closed_at=closed_at,
        actual_quantity_total=act_qty_total,
        actual_amount_total=act_amt_total,
        forecast_quantity_total=fcst_qty_total,
        budget_quantity_total=bud_qty_total,
        last_year_quantity_total=ly_qty_total,
        last_year_amount_total=ly_amt_total,
        forecast_accuracy_total=(act_qty_total / fcst_qty_total) if fcst_qty_total > 0 else None,
        yoy_growth_total=(act_qty_total / ly_qty_total) if ly_qty_total > 0 else None,
        budget_achievement_total=(act_qty_total / bud_qty_total) if bud_qty_total > 0 else None,
        rows=rows,
    )
