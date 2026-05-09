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
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Sequence

from src.backend.daily_sales_importer import DailyActualAggregate
from src.backend.database import MORDatabase
from src.backend.forecast_models import ForecastRow
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
    confidence: str          # "high" | "medium" | "low"


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

    # Single workday set covering the full lookback range used for cycle calculation
    history_start = today - timedelta(days=_HISTORY_LOOKBACK_DAYS)
    workday_set = fetch_workday_set(db, history_start, today)

    # Workdays remaining from tomorrow to month-end
    import calendar as _cal
    _, last_day = _cal.monthrange(year, month)
    month_end = date(year, month, last_day)
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

    # Build lookup: row_id → list of (shipment_date, quantity)
    history_map: dict[str, list[tuple[date, float]]] = {}
    for h in history_rows:
        raw = h["order_date"]
        d = date.fromisoformat(str(raw)[:10])
        key = f"{h['customer_name']}__{h['product_code']}"
        history_map.setdefault(key, []).append((d, float(h["qty"])))

    results: dict[str, ProjectionResult] = {}
    for row in active:
        actual = daily_actuals.get(row.row_id)
        current_qty = actual.actual_quantity if actual is not None else row.this_year_same_month_qty

        # Most recent shipment date: prefer current-month daily actual
        if actual is not None and actual.latest_sales_date is not None:
            raw_ls = actual.latest_sales_date
            latest_date: date | None = date.fromisoformat(str(raw_ls)[:10])
        else:
            latest_date = row.latest_order_date if row.latest_order_date else None

        entries = history_map.get(row.row_id, [])
        order_dates   = [e[0] for e in entries]
        order_quantities = [e[1] for e in entries]

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
    workday_cycle = _avg_workday_cycle(order_dates, workday_set, max_cycle_days)
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
    )


def _avg_workday_cycle(
    order_dates: list[date],
    workday_set: frozenset[date],
    max_days: int,
) -> int | None:
    """Average workday gap between consecutive order dates (capped at max_days)."""
    if len(order_dates) < 2:
        return None
    sorted_dates = sorted(order_dates)
    gaps = []
    for prev, curr in zip(sorted_dates, sorted_dates[1:]):
        gap = _workdays_between(prev, curr, workday_set)
        if 0 < gap <= max_days:
            gaps.append(gap)
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
