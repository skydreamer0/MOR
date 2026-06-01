"""Monthly review service.

All data comes from the DB — no Excel file dependency.

Data sources:
  actual       → daily_sales_actuals   (the closed month's imported records)
  forecast     → snapshot_items        (via month_close_records.final_snapshot_id)
  budget       → budget_targets
  last year    → daily_sales_actuals   if (year-1, month) is closed,
                 else sales_records    (synced from Excel)

Amounts:
  Primary amount is 含稅淨額 (tax-inclusive net of discount):
    daily_sales_actuals.taxed_amount
    sales_records.amount
    budget_targets.target_amount (same convention)
  Forecast amount is not stored at close time; it is derived via the
  amount_calculation seam from the period's own average unit price.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.backend.amount_calculation import (
    period_avg_unit_price,
    review_forecast_amount,
)
from src.backend.database import MORDatabase
from src.backend.row_identity import make_row_id, parse_row_id


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ReviewRow:
    """Per-row comparison: actual vs forecast vs budget vs last year.

    All amounts are 含稅淨額 (taxed net of discount).
    """
    customer_name: str
    product_code: str
    product_name: str
    # Quantities
    actual_quantity: float
    forecast_quantity: float
    budget_quantity: float
    last_year_quantity: float
    # Amounts (含稅淨額)
    actual_amount: float
    forecast_amount: float           # derived via amount_calculation.review_forecast_amount
    budget_amount: float
    last_year_amount: float
    # Quantity-side ratios
    forecast_gap: float              # actual_quantity - forecast_quantity
    forecast_accuracy: float | None  # actual / forecast (quantity)
    yoy_growth: float | None         # actual_qty / last_year_qty
    budget_achievement: float | None # actual_qty / budget_qty
    # Amount-side ratios
    forecast_amount_gap: float
    forecast_amount_accuracy: float | None
    yoy_amount_growth: float | None
    budget_amount_achievement: float | None
    # Amount-side absolute deltas (used to surface "金額大且偏移大" rows
    # ahead of "rate big but amount tiny" ones in growth/budget panels)
    yoy_amount_delta: float          # actual - last_year
    budget_amount_delta: float       # actual - budget


@dataclass(frozen=True)
class MonthlyReviewSummary:
    year: int
    month: int
    closed_at: str
    # Quantity totals
    actual_quantity_total: float
    forecast_quantity_total: float
    budget_quantity_total: float
    last_year_quantity_total: float
    # Amount totals (含稅淨額)
    actual_amount_total: float
    forecast_amount_total: float
    budget_amount_total: float
    last_year_amount_total: float
    # Quantity-side rates
    forecast_accuracy_total: float | None
    yoy_growth_total: float | None
    budget_achievement_total: float | None
    # Amount-side rates
    forecast_amount_accuracy_total: float | None
    yoy_amount_growth_total: float | None
    budget_amount_achievement_total: float | None
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
    name_map   = _load_product_names(db)
    fb_prices  = _load_fallback_prices(db, year, month)

    rows = _merge_rows(actuals, forecasts, budgets, last_year, name_map, fb_prices)
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
    """key = row identity. Aggregates qty and 含稅淨額."""
    with db.get_connection() as conn:
        rows = conn.execute(
            """
            SELECT customer_name, product_code,
                   MAX(product_name)    AS product_name,
                   SUM(actual_quantity) AS qty,
                   SUM(taxed_amount)    AS amount
            FROM   daily_sales_actuals
            WHERE  sales_year = ? AND sales_month = ?
            GROUP  BY customer_name, product_code
            """,
            (year, month),
        ).fetchall()
    return {
        make_row_id(r["customer_name"], r["product_code"]): {
            "customer_name": r["customer_name"],
            "product_code":  r["product_code"],
            "product_name":  r["product_name"] or "",
            "qty":           float(r["qty"] or 0),
            "amount":        float(r["amount"] or 0),
        }
        for r in rows
    }


def _load_product_names(db: MORDatabase) -> dict[str, str]:
    """Build product_code → product_name lookup from all available sources."""
    name_map: dict[str, str] = {}
    with db.get_connection() as conn:
        for sql in (
            "SELECT product_code, MAX(product_name) AS n FROM daily_sales_actuals "
            "WHERE product_name IS NOT NULL AND product_name != '' GROUP BY product_code",
            "SELECT product_code, MAX(product_name) AS n FROM sales_records "
            "WHERE product_name IS NOT NULL AND product_name != '' GROUP BY product_code",
            "SELECT product_code, MAX(product_name) AS n FROM current_month_records "
            "WHERE product_name IS NOT NULL AND product_name != '' GROUP BY product_code",
        ):
            for r in conn.execute(sql).fetchall():
                code = r["product_code"]
                if code and code not in name_map and r["n"]:
                    name_map[code] = r["n"]
    return name_map


def _load_fallback_prices(db: MORDatabase, year: int, month: int) -> dict[str, float]:
    """Most recent net unit price observed before the reviewed month.

    Used to derive a forecast amount for rows that had no actual sale this
    month (snapshot quantity is present but no period price exists).
    Keyed by row identity (customer, product).
    """
    prices: dict[str, float] = {}
    period_start = f"{year}-{month:02d}-01"
    with db.get_connection() as conn:
        # Closed months — weighted average 含稅淨額單價 over each row's history.
        for r in conn.execute(
            """
            SELECT customer_name, product_code,
                   SUM(taxed_amount)    AS amt,
                   SUM(actual_quantity) AS qty
            FROM   daily_sales_actuals
            WHERE  sales_date < ?
            GROUP  BY customer_name, product_code
            """,
            (period_start,),
        ).fetchall():
            qty = float(r["qty"] or 0)
            amt = float(r["amt"] or 0)
            if qty > 0 and amt > 0:
                prices[make_row_id(r["customer_name"], r["product_code"])] = amt / qty
        # sales_records — only fill rows still missing.
        for r in conn.execute(
            """
            SELECT customer_name, product_code,
                   SUM(quantity) AS qty,
                   SUM(amount)   AS amt
            FROM   sales_records
            WHERE  order_date < ?
            GROUP  BY customer_name, product_code
            """,
            (period_start,),
        ).fetchall():
            rid = make_row_id(r["customer_name"], r["product_code"])
            if rid in prices:
                continue
            qty = float(r["qty"] or 0)
            amt = float(r["amt"] or 0)
            if qty > 0 and amt > 0:
                prices[rid] = amt / qty
    return prices


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
        make_row_id(r["customer_name"], r["product_code"]): {
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
        make_row_id(r["customer_name"], r["product_code"]): {
            "target_quantity": float(r["target_quantity"] or 0),
            "target_amount":   float(r["target_amount"] or 0),
        }
        for r in rows
    }


def _load_last_year(db: MORDatabase, year: int, month: int) -> dict[str, dict]:
    """Prefer daily_sales_actuals for closed last-year months, fallback to sales_records.

    All amounts are 含稅淨額.
    """
    ly_year = year - 1

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
        make_row_id(r["customer_name"], r["product_code"]): {
            "qty":    float(r["qty"] or 0),
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
    name_map: dict[str, str] | None = None,
    fallback_prices: dict[str, float] | None = None,
) -> list[ReviewRow]:
    name_map = name_map or {}
    fallback_prices = fallback_prices or {}
    all_ids = set(actuals) | set(forecasts) | set(budgets)

    rows = []
    for row_id in all_ids:
        a  = actuals.get(row_id, {})
        f  = forecasts.get(row_id, {})
        b  = budgets.get(row_id, {})
        ly = last_year.get(row_id, {})

        identity = parse_row_id(row_id)

        act_qty  = a.get("qty", 0.0)
        act_amt  = a.get("amount", 0.0)
        fcst_qty = f.get("final_forecast", 0.0)
        bud_qty  = b.get("target_quantity", 0.0)
        bud_amt  = b.get("target_amount", 0.0)
        ly_qty   = ly.get("qty", 0.0)
        ly_amt   = ly.get("amount", 0.0)

        product_code = a.get("product_code", identity.product_code)
        product_name = a.get("product_name") or name_map.get(product_code, "")

        # 含稅淨額單價 — used solely to derive forecast amount; never displayed.
        period_price = period_avg_unit_price(act_qty, act_amt)
        fcst_amount  = review_forecast_amount(
            fcst_qty,
            period_unit_price=period_price,
            fallback_unit_price=fallback_prices.get(row_id, 0.0),
        )

        rows.append(ReviewRow(
            customer_name=a.get("customer_name", identity.customer_name),
            product_code=product_code,
            product_name=product_name,
            actual_quantity=act_qty,
            forecast_quantity=fcst_qty,
            budget_quantity=bud_qty,
            last_year_quantity=ly_qty,
            actual_amount=act_amt,
            forecast_amount=fcst_amount,
            budget_amount=bud_amt,
            last_year_amount=ly_amt,
            forecast_gap=act_qty - fcst_qty,
            forecast_accuracy=(act_qty / fcst_qty) if fcst_qty > 0 else None,
            yoy_growth=(act_qty / ly_qty) if ly_qty > 0 else None,
            budget_achievement=(act_qty / bud_qty) if bud_qty > 0 else None,
            forecast_amount_gap=act_amt - fcst_amount,
            forecast_amount_accuracy=(act_amt / fcst_amount) if fcst_amount > 0 else None,
            yoy_amount_growth=(act_amt / ly_amt) if ly_amt > 0 else None,
            budget_amount_achievement=(act_amt / bud_amt) if bud_amt > 0 else None,
            yoy_amount_delta=act_amt - ly_amt,
            budget_amount_delta=act_amt - bud_amt,
        ))

    rows.sort(key=lambda r: (r.customer_name, r.product_code))
    return rows


def _make_summary(
    year: int,
    month: int,
    closed_at: str,
    rows: list[ReviewRow],
) -> MonthlyReviewSummary:
    act_qty_total  = sum(r.actual_quantity    for r in rows)
    act_amt_total  = sum(r.actual_amount      for r in rows)
    fcst_qty_total = sum(r.forecast_quantity  for r in rows)
    fcst_amt_total = sum(r.forecast_amount    for r in rows)
    bud_qty_total  = sum(r.budget_quantity    for r in rows)
    bud_amt_total  = sum(r.budget_amount      for r in rows)
    ly_qty_total   = sum(r.last_year_quantity for r in rows)
    ly_amt_total   = sum(r.last_year_amount   for r in rows)

    return MonthlyReviewSummary(
        year=year,
        month=month,
        closed_at=closed_at,
        actual_quantity_total=act_qty_total,
        forecast_quantity_total=fcst_qty_total,
        budget_quantity_total=bud_qty_total,
        last_year_quantity_total=ly_qty_total,
        actual_amount_total=act_amt_total,
        forecast_amount_total=fcst_amt_total,
        budget_amount_total=bud_amt_total,
        last_year_amount_total=ly_amt_total,
        forecast_accuracy_total=(act_qty_total / fcst_qty_total) if fcst_qty_total > 0 else None,
        yoy_growth_total=(act_qty_total / ly_qty_total) if ly_qty_total > 0 else None,
        budget_achievement_total=(act_qty_total / bud_qty_total) if bud_qty_total > 0 else None,
        forecast_amount_accuracy_total=(act_amt_total / fcst_amt_total) if fcst_amt_total > 0 else None,
        yoy_amount_growth_total=(act_amt_total / ly_amt_total) if ly_amt_total > 0 else None,
        budget_amount_achievement_total=(act_amt_total / bud_amt_total) if bud_amt_total > 0 else None,
        rows=rows,
    )
