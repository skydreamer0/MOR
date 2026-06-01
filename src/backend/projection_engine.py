"""Month-end quantity projection model (Phase 4).

Replaces the coarse workday-ratio estimate with a cycle-driven model:

    estimated_eom_qty = current_qty + remaining_shipments × typical_qty_per_shipment

where:
  - workday_cycle   = historical average workday gap between consecutive shipments
  - remaining_shipments = how many more complete cycles fit before month-end
  - typical_qty_per_shipment = median historical shipment size

Confidence tiers:
  "high"   — ≥ 6 historical shipments, daily actuals available
  "medium" — ≥ 3 historical shipments
  "low"    — insufficient history; estimated_eom_qty falls back to current_qty
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Sequence

from src.backend.daily_sales_importer import DailyActualAggregate
from src.backend.database import MORDatabase
from src.backend.forecast_models import ForecastRow
from src.backend.row_identity import make_row_id
from src.backend.workday_calendar import fetch_workday_set


_HISTORY_LOOKBACK_DAYS = 730   # 2 years of calendar history for cycle calculation
_HIGH_CONFIDENCE_MIN  = 6
_MED_CONFIDENCE_MIN   = 3


@dataclass(frozen=True)
class ProjectionResult:
    estimated_eom_qty: float
    projected_remaining_qty: float
    remaining_shipments: int
    typical_qty_per_shipment: float
    workday_cycle: int | None
    confidence: str                          # "high" | "medium" | "low"
    gap_history: list[int] = field(default_factory=list)  # workday gaps, oldest→newest, max 8


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def batch_project_eom(
    db: MORDatabase,
    rows: Sequence[ForecastRow],
    daily_actuals: dict[str, DailyActualAggregate],
    today: date,
    year: int,
    month: int,
    max_cycle_days: int = 120,
) -> dict[str, ProjectionResult]:
    """Compute ProjectionResult for every non-excluded ForecastRow.

    One DB query fetches all relevant sales_records history, then each row's
    projection is computed in-memory.
    """
    active = [r for r in rows if not r.excluded]
    if not active:
        return {}

    import calendar as _cal
    _, last_day = _cal.monthrange(year, month)
    month_end = date(year, month, last_day)

    # Single workday set covering the full lookback range plus through month-end
    # (must extend to month_end so workdays_remaining calculation finds future dates)
    history_start = today - timedelta(days=_HISTORY_LOOKBACK_DAYS)
    workday_set = fetch_workday_set(db, history_start, month_end)

    workdays_remaining = sum(1 for d in workday_set if today < d <= month_end)

    # Fetch historical shipments (excluding current month)
    current_month_prefix = f"{year}-{month:02d}"
    customer_names = list({r.customer for r in active})
    product_codes  = list({r.product_code for r in active})
    placeholders_c = ",".join("?" * len(customer_names))
    placeholders_p = ",".join("?" * len(product_codes))

    with db.get_connection() as conn:
        history_rows = conn.execute(
            f"""
            SELECT order_date, customer_name, product_code, SUM(quantity) AS qty
            FROM   sales_records
            WHERE  customer_name IN ({placeholders_c})
              AND  product_code  IN ({placeholders_p})
              AND  strftime('%Y-%m', order_date) != ?
            GROUP  BY order_date, customer_name, product_code
            ORDER  BY customer_name, product_code, order_date
            """,
            customer_names + product_codes + [current_month_prefix],
        ).fetchall()

        # Current month's per-date shipments from daily imports (daily_sales_actuals).
        # These are excluded from sales_records (not yet closed), so we append them
        # so that gap/cycle calculations include the most recent shipment dates.
        curr_month_rows = conn.execute(
            f"""
            SELECT sales_date AS order_date, customer_name, product_code,
                   SUM(actual_quantity) AS qty
            FROM   daily_sales_actuals
            WHERE  sales_year = ? AND sales_month = ?
              AND  customer_name IN ({placeholders_c})
              AND  product_code  IN ({placeholders_p})
            GROUP  BY sales_date, customer_name, product_code
            ORDER  BY customer_name, product_code, sales_date
            """,
            [year, month] + customer_names + product_codes,
        ).fetchall()

    # pack_factor per row_id — used to convert curr_month raw units to display units
    pack_map = {
        row.row_id: (row.price_quantity if row.price_quantity > 0 else 1.0)
        for row in active
    }

    # Build lookup: row_id → list of (shipment_date, quantity), oldest → newest
    history_map: dict[str, list[tuple[date, float]]] = {}
    for h in history_rows:
        raw = h["order_date"]
        d = date.fromisoformat(str(raw)[:10])
        key = make_row_id(h["customer_name"], h["product_code"])
        history_map.setdefault(key, []).append((d, float(h["qty"])))

    for h in curr_month_rows:
        raw = h["order_date"]
        d = date.fromisoformat(str(raw)[:10])
        key = make_row_id(h["customer_name"], h["product_code"])
        # daily_sales_actuals stores raw (smallest-package) units; convert to
        # display units here so quantities are on the same scale as sales_records.
        pack = pack_map.get(key, 1.0)
        history_map.setdefault(key, []).append((d, float(h["qty"]) * pack))

    # Re-sort each entry to ensure chronological order after merging two sources
    for key in history_map:
        history_map[key].sort(key=lambda x: x[0])

    results: dict[str, ProjectionResult] = {}
    for row in active:
        actual = daily_actuals.get(row.row_id)
        _pack = row.price_quantity if row.price_quantity > 0 else 1.0
        current_qty = (actual.actual_quantity * _pack) if actual is not None else row.this_year_same_month_qty

        # Most recent shipment date: prefer current-month daily actual
        if actual is not None and actual.latest_sales_date is not None:
            raw_ls = actual.latest_sales_date
            latest_date: date | None = date.fromisoformat(str(raw_ls)[:10])
        else:
            latest_date = row.latest_order_date if row.latest_order_date else None

        entries = history_map.get(row.row_id, [])
        order_dates   = [e[0] for e in entries]
        # Use only the most recent 20 orders for typical qty so that old volume
        # patterns (e.g. pre-price-change bulk orders) don't skew the median.
        order_quantities = [e[1] for e in entries[-20:]]

        results[row.row_id] = _project(
            order_dates=order_dates,
            order_quantities=order_quantities,
            workday_set=workday_set,
            current_qty=current_qty,
            latest_sales_date=latest_date,
            today=today,
            workdays_remaining=workdays_remaining,
            has_daily_actual=actual is not None,
            max_cycle_days=max_cycle_days,
        )
    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _project(
    order_dates: list[date],
    order_quantities: list[float],
    workday_set: frozenset[date],
    current_qty: float,
    latest_sales_date: date | None,
    today: date,
    workdays_remaining: int,
    has_daily_actual: bool,
    max_cycle_days: int,
) -> ProjectionResult:
    gaps          = _workday_gaps(order_dates, workday_set, max_cycle_days)
    workday_cycle = (max(1, round(sum(gaps) / len(gaps))) if gaps else None)
    typical_qty   = _typical_shipment_qty(order_quantities)
    n_shipments   = len(order_dates)

    if workday_cycle is None or workday_cycle <= 0 or typical_qty <= 0:
        return ProjectionResult(
            estimated_eom_qty=current_qty,
            projected_remaining_qty=0.0,
            remaining_shipments=0,
            typical_qty_per_shipment=typical_qty,
            workday_cycle=workday_cycle,
            confidence="low",
            gap_history=gaps,
        )

    # Workdays elapsed since last shipment
    if latest_sales_date is not None:
        days_since = _workdays_between(latest_sales_date, today, workday_set)
    else:
        days_since = workday_cycle  # no reference → assume start of new cycle

    # Remaining shipments: account for time already elapsed in current cycle
    workdays_until_next = max(0, workday_cycle - days_since)
    if workdays_remaining < workdays_until_next:
        remaining = 0
    else:
        remaining = 1 + (workdays_remaining - workdays_until_next) // workday_cycle

    projected_remaining = remaining * typical_qty
    estimated_eom = current_qty + projected_remaining

    confidence = _confidence(n_shipments, has_daily_actual)
    return ProjectionResult(
        estimated_eom_qty=estimated_eom,
        projected_remaining_qty=projected_remaining,
        remaining_shipments=remaining,
        typical_qty_per_shipment=typical_qty,
        workday_cycle=workday_cycle,
        confidence=confidence,
        gap_history=gaps,
    )


def _workday_gaps(
    order_dates: list[date],
    workday_set: frozenset[date],
    max_days: int,
) -> list[int]:
    """Workday gaps between consecutive order dates, capped and limited to last 8."""
    if len(order_dates) < 2:
        return []
    sorted_dates = sorted(order_dates)
    gaps = []
    for prev, curr in zip(sorted_dates, sorted_dates[1:]):
        gap = _workdays_between(prev, curr, workday_set)
        if 0 < gap <= max_days:
            gaps.append(gap)
    return gaps[-8:]


def _avg_workday_cycle(
    order_dates: list[date],
    workday_set: frozenset[date],
    max_days: int,
) -> int | None:
    """Average workday gap between consecutive order dates (capped at max_days)."""
    gaps = _workday_gaps(order_dates, workday_set, max_days)
    if not gaps:
        return None
    return max(1, round(sum(gaps) / len(gaps)))


def _typical_shipment_qty(quantities: list[float]) -> float:
    """Median shipment quantity; 0.0 if no data."""
    filtered = [q for q in quantities if q > 0]
    if not filtered:
        return 0.0
    return statistics.median(filtered)


def _workdays_between(start: date, end: date, workday_set: frozenset[date]) -> int:
    """Workdays in (start, end] — uses workday_set; falls back to Mon–Fri for uncovered dates."""
    if start >= end:
        return 0
    count = 0
    d = start + timedelta(days=1)
    while d <= end:
        if d in workday_set:
            count += 1
        else:
            # Date outside the fetched range: approximate with Mon–Fri
            count += 1 if d.weekday() < 5 else 0
        d += timedelta(days=1)
    return count


def _confidence(n_shipments: int, has_daily_actual: bool) -> str:
    if n_shipments >= _HIGH_CONFIDENCE_MIN and has_daily_actual:
        return "high"
    if n_shipments >= _MED_CONFIDENCE_MIN:
        return "medium"
    return "low"
