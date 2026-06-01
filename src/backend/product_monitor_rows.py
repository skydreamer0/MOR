from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from typing import Callable, Iterable, Mapping

from src.backend.daily_sales_importer import DailyActualAggregate
from src.backend.forecast_models import ForecastRow
from src.backend.projection_engine import ProjectionResult
from src.backend.row_identity import make_row_id
from src.backend.workday_calendar import fetch_workday_set


DROP_RISK_THRESHOLD = 0.9

_CYCLE_HIGH_MULTIPLIER = 1.2
_CYCLE_CAUTION_MULTIPLIER = 0.8

AmountForQuantity = Callable[[float, ForecastRow], float]


@dataclass(frozen=True)
class ProductMonitorRow:
    customer: str
    product_code: str
    product_name: str
    last_year_quantity: float
    last_month_quantity: float
    current_quantity: float
    forecast_quantity: float
    diff_quantity: float
    drop_rate: float | None
    status: str
    status_key: str
    note: str
    latest_price: float = 0.0
    amount_impact: float = 0.0
    latest_order_date: date | None = None
    days_since_last_shipment_workdays: int | None = None
    estimated_eom_qty: float = 0.0
    yoy_growth_rate: float | None = None
    budget_achievement_rate: float | None = None
    cycle_status: str = "no_cycle"
    cycle_days: int | None = None
    budget_quantity: float = 0.0
    remaining_shipments: int = 0
    typical_qty_per_shipment: float = 0.0
    projection_confidence: str = "low"
    current_taxed_amount: float = 0.0
    estimated_eom_amount: float = 0.0
    final_forecast_amount: float = 0.0
    last_year_amount: float = 0.0
    budget_amount: float = 0.0
    gap_history: list[int] = field(default_factory=list)
    gap_trend: str = "none"
    gap_trend_delta: int = 0
    monthly_history: list[dict] = field(default_factory=list)


def build_product_monitor_rows(
    rows: Iterable[ForecastRow],
    daily_actuals: Mapping[str, DailyActualAggregate] | None = None,
    db=None,
    today: date | None = None,
    projections: Mapping[str, ProjectionResult] | None = None,
    target_month: int = 0,
    *,
    amount_for_quantity: AmountForQuantity,
) -> list[ProductMonitorRow]:
    today = today or date.today()
    actuals = daily_actuals or {}
    projs = projections or {}
    workday_set = fetch_workday_set(db, today - timedelta(days=400), today) if db is not None else None

    active_rows = [row for row in rows if not row.excluded]
    monitor_rows = [
        _to_monitor_row(
            row,
            actuals.get(row.row_id),
            workday_set,
            today,
            projs.get(row.row_id),
            target_month,
            amount_for_quantity=amount_for_quantity,
        )
        for row in active_rows
    ]

    if db is not None:
        closed_months = _get_last_closed_months(db, 6)
        if closed_months:
            row_ids = [(r.customer, r.product_code) for r in active_rows]
            histories = _fetch_monthly_history(db, row_ids, closed_months)
            monitor_rows = [
                replace(r, monthly_history=histories.get(make_row_id(r.customer, r.product_code), []))
                for r in monitor_rows
            ]

    status_order = {"high": 0, "caution": 1, "ok": 2, "no_history": 3}
    return sorted(
        monitor_rows,
        key=lambda r: (
            status_order.get(r.status_key, 3),
            r.budget_achievement_rate if r.budget_achievement_rate is not None else float("inf"),
            r.yoy_growth_rate if r.yoy_growth_rate is not None else float("inf"),
            -(r.days_since_last_shipment_workdays or 0),
        ),
    )


def is_high_risk_drop(row: ForecastRow) -> bool:
    return row.last_year_same_month_qty > 0 and row.final_forecast < row.last_year_same_month_qty * DROP_RISK_THRESHOLD


def _get_last_closed_months(db, n: int) -> list[tuple[int, int]]:
    """Return the last n closed (year, month) pairs, newest first."""
    with db.get_connection() as conn:
        rows = conn.execute(
            "SELECT year, month FROM month_close_records ORDER BY year DESC, month DESC LIMIT ?",
            (n,),
        ).fetchall()
    return [(r["year"], r["month"]) for r in rows]


def _fetch_monthly_history(
    db,
    row_ids: list[tuple[str, str]],
    closed_months: list[tuple[int, int]],
) -> dict[str, list[dict]]:
    """Batch-fetch actual / budget / last-year qty for each row identity."""
    if not row_ids or not closed_months:
        return {}

    month_strs = [f"{y}-{m:02d}" for y, m in closed_months]
    ly_month_strs = [f"{y - 1}-{m:02d}" for y, m in closed_months]

    customers = list({r[0] for r in row_ids})
    products = list({r[1] for r in row_ids})
    ph_c = ",".join("?" * len(customers))
    ph_p = ",".join("?" * len(products))
    ph_m = ",".join("?" * len(month_strs))
    ph_ly = ",".join("?" * len(ly_month_strs))

    with db.get_connection() as conn:
        actuals = conn.execute(
            f"""SELECT CAST(strftime('%Y', order_date) AS INTEGER) AS yr,
                       CAST(strftime('%m', order_date) AS INTEGER) AS mo,
                       customer_name, product_code, SUM(quantity) AS qty
                FROM   sales_records
                WHERE  strftime('%Y-%m', order_date) IN ({ph_m})
                  AND  customer_name IN ({ph_c})
                  AND  product_code  IN ({ph_p})
                GROUP  BY yr, mo, customer_name, product_code""",
            month_strs + customers + products,
        ).fetchall()

        ly_actuals = conn.execute(
            f"""SELECT CAST(strftime('%Y', order_date) AS INTEGER) + 1 AS yr,
                       CAST(strftime('%m', order_date) AS INTEGER)     AS mo,
                       customer_name, product_code, SUM(quantity) AS qty
                FROM   sales_records
                WHERE  strftime('%Y-%m', order_date) IN ({ph_ly})
                  AND  customer_name IN ({ph_c})
                  AND  product_code  IN ({ph_p})
                GROUP  BY yr, mo, customer_name, product_code""",
            ly_month_strs + customers + products,
        ).fetchall()

        budget_clauses = " OR ".join(["(year=? AND month=?)"] * len(closed_months))
        budget_params = [v for y, m in closed_months for v in (y, m)]
        budgets = conn.execute(
            f"""SELECT year, month, customer_name, product_code, target_quantity
                FROM   budget_targets
                WHERE  ({budget_clauses})
                  AND  customer_name IN ({ph_c})
                  AND  product_code  IN ({ph_p})""",
            budget_params + customers + products,
        ).fetchall()

    actual_map = {
        (r["customer_name"], r["product_code"], r["yr"], r["mo"]): float(r["qty"])
        for r in actuals
    }
    ly_map = {
        (r["customer_name"], r["product_code"], r["yr"], r["mo"]): float(r["qty"])
        for r in ly_actuals
    }
    budget_map = {
        (r["customer_name"], r["product_code"], r["year"], r["month"]): float(r["target_quantity"])
        for r in budgets
    }

    result: dict[str, list[dict]] = {}
    for customer, product_code in row_ids:
        key = make_row_id(customer, product_code)
        history = []
        for y, m in closed_months:
            history.append({
                "year": y,
                "month": m,
                "label": f"{m:02d}月",
                "actual": actual_map.get((customer, product_code, y, m), 0.0),
                "budget": budget_map.get((customer, product_code, y, m), 0.0),
                "last_year": ly_map.get((customer, product_code, y, m), 0.0),
            })
        result[key] = history
    return result


def _days_since_order(workday_set: frozenset[date], order_date: date, today: date) -> int:
    """Count workdays strictly after order_date up to and including today."""
    return sum(1 for d in workday_set if order_date < d <= today)


def _compute_gap_trend(gaps: list[int]) -> tuple[str, int]:
    """Compare the most recent 3 gaps to the overall average."""
    if len(gaps) < 3:
        return "none", 0
    overall_avg = sum(gaps) / len(gaps)
    recent_avg = sum(gaps[-3:]) / 3
    delta = round(recent_avg - overall_avg)
    if overall_avg == 0:
        return "none", 0
    if recent_avg > overall_avg * 1.10:
        return "rising", delta
    if recent_avg < overall_avg * 0.90:
        return "falling", delta
    return "stable", delta


def _cycle_status_info(days_since: int | None, cycle_days: int | None) -> tuple[str, bool, bool]:
    """Return (cycle_status_key, is_high_risk, is_caution)."""
    if days_since is None or cycle_days is None or cycle_days <= 0:
        return "no_cycle", False, False
    if days_since > cycle_days * _CYCLE_HIGH_MULTIPLIER:
        return "delayed", True, False
    if days_since >= cycle_days * _CYCLE_CAUTION_MULTIPLIER:
        return "approaching", False, True
    return "ok", False, False


def _three_axis_status(
    yoy_rate: float | None,
    bud_rate: float | None,
    cycle_high: bool,
    cycle_caution: bool,
    last_year_qty: float,
    budget_qty: float,
) -> tuple[str, str]:
    """Derive (status_display, status_key) from the three monitoring axes."""
    has_comparison = last_year_qty > 0 or budget_qty > 0
    if not has_comparison and not cycle_high and not cycle_caution:
        return "無去年同期", "no_history"

    if (
        (yoy_rate is not None and yoy_rate < DROP_RISK_THRESHOLD)
        or (bud_rate is not None and bud_rate < DROP_RISK_THRESHOLD)
        or cycle_high
    ):
        return "高風險", "high"

    if (
        (yoy_rate is not None and yoy_rate < 1.0)
        or (bud_rate is not None and bud_rate < 1.0)
        or cycle_caution
    ):
        return "注意", "caution"

    return "正常/成長", "ok"


def _to_monitor_row(
    row: ForecastRow,
    actual: DailyActualAggregate | None = None,
    workday_set: frozenset[date] | None = None,
    today: date | None = None,
    projection: ProjectionResult | None = None,
    target_month: int = 0,
    *,
    amount_for_quantity: AmountForQuantity,
) -> ProductMonitorRow:
    today = today or date.today()

    pack_factor = row.price_quantity if row.price_quantity > 0 else 1.0
    raw_current = actual.actual_quantity if actual is not None else None

    days_since: int | None = None
    if workday_set is not None:
        reference_date: date | None = None
        if actual is not None and actual.latest_sales_date is not None:
            raw_ls = actual.latest_sales_date
            reference_date = date.fromisoformat(str(raw_ls)[:10])
        elif row.latest_order_date:
            reference_date = row.latest_order_date
        if reference_date is not None:
            days_since = _days_since_order(workday_set, reference_date, today)

    yoy_rate = (row.final_forecast / row.last_year_same_month_qty) if row.last_year_same_month_qty > 0 else None
    bud_rate = (row.final_forecast / row.budget_quantity) if row.budget_quantity > 0 else None

    cycle_status_key, cycle_high, cycle_caution = _cycle_status_info(days_since, row.cycle_days)
    status, status_key = _three_axis_status(
        yoy_rate,
        bud_rate,
        cycle_high,
        cycle_caution,
        row.last_year_same_month_qty,
        row.budget_quantity,
    )

    diff_quantity = row.final_forecast - row.last_year_same_month_qty
    drop_rate = (diff_quantity / row.last_year_same_month_qty * 100) if row.last_year_same_month_qty > 0 else None
    amount_impact = amount_for_quantity(diff_quantity, row)

    if projection is not None:
        raw_estimated_eom = projection.estimated_eom_qty
        remaining_shipments = projection.remaining_shipments
        raw_typical_qty = projection.typical_qty_per_shipment
        proj_confidence = projection.confidence
        projected_remaining_qty = projection.projected_remaining_qty
        gap_history = projection.gap_history
    else:
        raw_estimated_eom = row.system_forecast
        remaining_shipments = 0
        raw_typical_qty = 0.0
        proj_confidence = "low"
        projected_remaining_qty = 0.0
        gap_history = []

    gap_trend, gap_trend_delta = _compute_gap_trend(gap_history)

    current_taxed_amount = float(actual.taxed_amount) if actual is not None else 0.0
    display_current = raw_current * pack_factor if raw_current is not None else row.this_year_same_month_qty
    if display_current > 0 and current_taxed_amount > 0:
        implied_unit_price = current_taxed_amount / display_current
    else:
        implied_unit_price = row.latest_price
    estimated_eom_amount = current_taxed_amount + projected_remaining_qty * implied_unit_price
    final_forecast_amount = float(row.estimated_amount)
    last_year_amount = (
        float(row.ly_monthly_amount[target_month - 1])
        if 1 <= target_month <= 12 else 0.0
    )
    budget_amount = float(row.budget_amount)

    return ProductMonitorRow(
        customer=row.customer,
        product_code=row.product_code,
        product_name=row.product_name,
        last_year_quantity=row.last_year_same_month_qty,
        last_month_quantity=row.last_month_actual,
        current_quantity=display_current,
        forecast_quantity=row.final_forecast,
        diff_quantity=diff_quantity,
        drop_rate=drop_rate,
        status=status,
        status_key=status_key,
        note=row.adjustment_reason or "",
        latest_price=row.latest_price,
        amount_impact=amount_impact,
        latest_order_date=row.latest_order_date,
        days_since_last_shipment_workdays=days_since,
        estimated_eom_qty=raw_estimated_eom,
        yoy_growth_rate=yoy_rate,
        budget_achievement_rate=bud_rate,
        cycle_status=cycle_status_key,
        cycle_days=projection.workday_cycle if projection is not None else row.cycle_days,
        budget_quantity=row.budget_quantity,
        remaining_shipments=remaining_shipments,
        typical_qty_per_shipment=raw_typical_qty,
        projection_confidence=proj_confidence,
        current_taxed_amount=current_taxed_amount,
        estimated_eom_amount=estimated_eom_amount,
        final_forecast_amount=final_forecast_amount,
        last_year_amount=last_year_amount,
        budget_amount=budget_amount,
        gap_history=gap_history,
        gap_trend=gap_trend,
        gap_trend_delta=gap_trend_delta,
    )
