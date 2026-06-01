"""Systemic forecast-bias detector.

Looks at the last N closed months. For each (customer, product) row that has a
forecast in each of those months, compute the signed accuracy ratio
  ratio = actual_amount / forecast_amount       (含稅淨額 throughout)
Then flag rows whose AVERAGE absolute deviation from 1.0 exceeds a threshold
across the window — these are the rows whose stored forecast is consistently
wrong in the same direction, i.e. the forecasting logic for these rows needs
a correction.

This is meant to be a focused signal (~10 worst offenders), not a full audit.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.backend.database import MORDatabase


LOOKBACK_MONTHS = 3
BIAS_THRESHOLD  = 0.15           # |1 - avg ratio| >= 15% over the window
BIAS_LIST_LIMIT = 10


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BiasRow:
    customer_name: str
    product_code: str
    product_name: str
    avg_accuracy: float              # average actual / forecast over the window
    months_observed: int
    direction: str                   # "over" == 系統性高估 (predict>actual)
                                     # "under" == 系統性低估 (predict<actual)


@dataclass(frozen=True)
class ForecastBias:
    lookback_months: int
    over_forecast: list[BiasRow]     # avg actual/forecast < 1 - threshold
    under_forecast: list[BiasRow]    # avg actual/forecast > 1 + threshold


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_forecast_bias(
    db: MORDatabase,
    year: int,
    month: int,
    lookback: int = LOOKBACK_MONTHS,
) -> ForecastBias:
    months = _last_n_closed_months(db, year, month, lookback)
    if not months:
        return ForecastBias(lookback_months=lookback, over_forecast=[], under_forecast=[])

    # Collect actual/forecast pairs per (customer, product) per month
    samples: dict[tuple[str, str], list[float]] = {}
    name_map: dict[str, str] = {}
    for y, m in months:
        actuals  = _actual_amounts(db, y, m)
        forecast = _forecast_amounts(db, y, m)
        for key, fcst_amt in forecast.items():
            if fcst_amt <= 0:
                continue
            act_amt = actuals.get(key, 0.0)
            ratio = act_amt / fcst_amt
            samples.setdefault(key, []).append(ratio)
        for (_, prod), name in _names_for_month(db, y, m).items():
            if prod not in name_map and name:
                name_map[prod] = name

    over, under = [], []
    for (customer, product), ratios in samples.items():
        if len(ratios) < lookback:
            continue  # need a sample for every month in the window
        avg = sum(ratios) / len(ratios)
        if abs(1 - avg) < BIAS_THRESHOLD:
            continue
        row = BiasRow(
            customer_name=customer,
            product_code=product,
            product_name=name_map.get(product, ""),
            avg_accuracy=avg,
            months_observed=len(ratios),
            direction="over" if avg < 1.0 else "under",
        )
        (over if row.direction == "over" else under).append(row)

    over.sort(key=lambda r: r.avg_accuracy)            # most-over first
    under.sort(key=lambda r: -r.avg_accuracy)          # most-under first
    return ForecastBias(
        lookback_months=lookback,
        over_forecast=over[:BIAS_LIST_LIMIT],
        under_forecast=under[:BIAS_LIST_LIMIT],
    )


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def _last_n_closed_months(
    db: MORDatabase, year: int, month: int, n: int,
) -> list[tuple[int, int]]:
    """Return the n most-recent closed months ending at (year, month), oldest first.

    Only months with a final_snapshot_id qualify — we need a stored forecast to
    compare against.
    """
    candidates: list[tuple[int, int]] = []
    y, m = year, month
    for _ in range(n):
        candidates.append((y, m))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    candidates.reverse()
    with db.get_connection() as conn:
        out = []
        for y, m in candidates:
            r = conn.execute(
                """SELECT id FROM month_close_records
                WHERE year = ? AND month = ? AND final_snapshot_id IS NOT NULL""",
                (y, m),
            ).fetchone()
            if r:
                out.append((y, m))
    return out


def _actual_amounts(db: MORDatabase, year: int, month: int) -> dict[tuple[str, str], float]:
    with db.get_connection() as conn:
        rows = conn.execute(
            """SELECT customer_name, product_code, SUM(taxed_amount) AS amt
            FROM daily_sales_actuals
            WHERE sales_year = ? AND sales_month = ?
            GROUP BY customer_name, product_code""",
            (year, month),
        ).fetchall()
    return {(r["customer_name"], r["product_code"]): float(r["amt"] or 0) for r in rows}


def _forecast_amounts(db: MORDatabase, year: int, month: int) -> dict[tuple[str, str], float]:
    """Forecast amount derived the same way as monthly_review: forecast_qty * 該月平均含稅單價."""
    with db.get_connection() as conn:
        snap = conn.execute(
            """SELECT final_snapshot_id FROM month_close_records
            WHERE year = ? AND month = ?""",
            (year, month),
        ).fetchone()
        if not snap or snap["final_snapshot_id"] is None:
            return {}
        sid = snap["final_snapshot_id"]
        fcst_rows = conn.execute(
            """SELECT customer_name, product_code, final_forecast
            FROM snapshot_items WHERE snapshot_id = ?""",
            (sid,),
        ).fetchall()
        actuals = conn.execute(
            """SELECT customer_name, product_code,
                      SUM(actual_quantity) AS qty,
                      SUM(taxed_amount)    AS amt
            FROM daily_sales_actuals
            WHERE sales_year = ? AND sales_month = ?
            GROUP BY customer_name, product_code""",
            (year, month),
        ).fetchall()
    price = {
        (r["customer_name"], r["product_code"]):
            (float(r["amt"] or 0) / float(r["qty"])) if r["qty"] else 0.0
        for r in actuals
    }
    out: dict[tuple[str, str], float] = {}
    for r in fcst_rows:
        qty = float(r["final_forecast"] or 0)
        p   = price.get((r["customer_name"], r["product_code"]), 0.0)
        if qty > 0 and p > 0:
            out[(r["customer_name"], r["product_code"])] = qty * p
    return out


def _names_for_month(
    db: MORDatabase, year: int, month: int,
) -> dict[tuple[str, str], str]:
    with db.get_connection() as conn:
        rows = conn.execute(
            """SELECT customer_name, product_code, MAX(product_name) AS n
            FROM daily_sales_actuals
            WHERE sales_year = ? AND sales_month = ?
            GROUP BY customer_name, product_code""",
            (year, month),
        ).fetchall()
    return {(r["customer_name"], r["product_code"]): (r["n"] or "") for r in rows}
