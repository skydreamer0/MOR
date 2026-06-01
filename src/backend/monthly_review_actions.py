"""Monthly review action lists.

Builds four business-actionable customer lists for the reviewed month:

  失聯名單   lost     去年同月有買、今年同月沒買的客戶
  優先拜訪   priority YoY 金額跌幅 >= 20% 且金額屬本月前 20% 的大客戶
  流失中     declining 近 3 個月金額逐月下滑的客戶
  新業務     new      今年同月有買、去年同月沒買的客戶

All amounts are 含稅淨額:
  daily_sales_actuals.taxed_amount  for closed months
  sales_records.amount              for fallback
"""
from __future__ import annotations

from dataclasses import dataclass

from src.backend.database import MORDatabase


# ---------------------------------------------------------------------------
# Thresholds — kept as module constants so they can be reviewed in one place.
# ---------------------------------------------------------------------------

YOY_DROP_THRESHOLD = 0.20            # 20% decline triggers "priority visit"
PRIORITY_TOP_SHARE = 0.20            # top 20% of current-month amount
DECLINING_LOOKBACK_MONTHS = 3        # consecutive months of decline
ACTION_LIST_LIMIT = 10               # max rows per list shown in UI


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LostCustomer:
    customer_name: str
    last_year_amount: float          # 含稅淨額


@dataclass(frozen=True)
class PriorityVisitCustomer:
    customer_name: str
    current_amount: float            # 含稅淨額
    last_year_amount: float          # 含稅淨額
    yoy_drop: float                  # 0.30 == 30% drop


@dataclass(frozen=True)
class DecliningCustomer:
    customer_name: str
    trend: list[float]               # length == DECLINING_LOOKBACK_MONTHS, oldest first


@dataclass(frozen=True)
class NewCustomer:
    customer_name: str
    current_amount: float            # 含稅淨額


@dataclass(frozen=True)
class ActionLists:
    lost:     list[LostCustomer]
    priority: list[PriorityVisitCustomer]
    declining: list[DecliningCustomer]
    new:      list[NewCustomer]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_action_lists(db: MORDatabase, year: int, month: int) -> ActionLists:
    current   = _customer_amounts(db, year, month)
    last_year = _customer_amounts(db, year - 1, month)
    trends    = _recent_customer_amounts(db, year, month, DECLINING_LOOKBACK_MONTHS)

    return ActionLists(
        lost=_build_lost(current, last_year),
        priority=_build_priority(current, last_year),
        declining=_build_declining(trends),
        new=_build_new(current, last_year),
    )


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def _customer_amounts(db: MORDatabase, year: int, month: int) -> dict[str, float]:
    """Return {customer_name: 含稅淨額} for one calendar month.

    Prefers daily_sales_actuals.taxed_amount when that month is closed;
    otherwise reads sales_records.amount.
    """
    with db.get_connection() as conn:
        closed = conn.execute(
            "SELECT id FROM month_close_records WHERE year = ? AND month = ?",
            (year, month),
        ).fetchone()

        if closed:
            rows = conn.execute(
                """
                SELECT customer_name, SUM(taxed_amount) AS amt
                FROM   daily_sales_actuals
                WHERE  sales_year = ? AND sales_month = ?
                GROUP  BY customer_name
                """,
                (year, month),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT customer_name, SUM(amount) AS amt
                FROM   sales_records
                WHERE  strftime('%Y', order_date) = ?
                  AND  strftime('%m', order_date) = ?
                GROUP  BY customer_name
                """,
                (str(year), f"{month:02d}"),
            ).fetchall()

    return {r["customer_name"]: float(r["amt"] or 0) for r in rows if r["customer_name"]}


def _recent_customer_amounts(
    db: MORDatabase, year: int, month: int, lookback: int,
) -> dict[str, list[float]]:
    """Return {customer_name: [amt_oldest, ..., amt_current]} over `lookback` months."""
    months = _last_n_months(year, month, lookback)
    trends: dict[str, list[float]] = {}
    for idx, (y, m) in enumerate(months):
        amounts = _customer_amounts(db, y, m)
        for customer, amt in amounts.items():
            trend = trends.setdefault(customer, [0.0] * lookback)
            trend[idx] = amt
    return trends


def _last_n_months(year: int, month: int, n: int) -> list[tuple[int, int]]:
    """Return [(y, m), ...] for the n months ending at (year, month), oldest first."""
    out: list[tuple[int, int]] = []
    y, m = year, month
    for _ in range(n):
        out.append((y, m))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return list(reversed(out))


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def _build_lost(current: dict[str, float], last_year: dict[str, float]) -> list[LostCustomer]:
    out = [
        LostCustomer(customer_name=c, last_year_amount=amt)
        for c, amt in last_year.items()
        if amt > 0 and current.get(c, 0) <= 0
    ]
    out.sort(key=lambda x: -x.last_year_amount)
    return out[:ACTION_LIST_LIMIT]


def _build_priority(
    current: dict[str, float], last_year: dict[str, float],
) -> list[PriorityVisitCustomer]:
    if not current:
        return []
    # Top-20% threshold on current-month amount.
    top_cutoff = _percentile_floor(list(current.values()), 1.0 - PRIORITY_TOP_SHARE)
    candidates = []
    for customer, cur_amt in current.items():
        ly_amt = last_year.get(customer, 0.0)
        if cur_amt < top_cutoff or ly_amt <= 0:
            continue
        drop = (ly_amt - cur_amt) / ly_amt
        if drop >= YOY_DROP_THRESHOLD:
            candidates.append(PriorityVisitCustomer(
                customer_name=customer,
                current_amount=cur_amt,
                last_year_amount=ly_amt,
                yoy_drop=drop,
            ))
    candidates.sort(key=lambda x: -x.yoy_drop)
    return candidates[:ACTION_LIST_LIMIT]


def _build_declining(trends: dict[str, list[float]]) -> list[DecliningCustomer]:
    out = []
    for customer, trend in trends.items():
        if len(trend) < 2:
            continue
        if any(trend[i] >= trend[i - 1] or trend[i] <= 0 for i in range(1, len(trend))):
            continue  # not strictly decreasing or has a zero gap
        out.append(DecliningCustomer(customer_name=customer, trend=trend))
    out.sort(key=lambda x: x.trend[-1] - x.trend[0])  # biggest absolute decline first
    return out[:ACTION_LIST_LIMIT]


def _build_new(current: dict[str, float], last_year: dict[str, float]) -> list[NewCustomer]:
    out = [
        NewCustomer(customer_name=c, current_amount=amt)
        for c, amt in current.items()
        if amt > 0 and last_year.get(c, 0) <= 0
    ]
    out.sort(key=lambda x: -x.current_amount)
    return out[:ACTION_LIST_LIMIT]


def _percentile_floor(values: list[float], q: float) -> float:
    """Return the smallest value in the top (1-q) portion. q=0.8 → top-20% cutoff."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = max(0, min(len(sorted_vals) - 1, int(len(sorted_vals) * q)))
    return sorted_vals[idx]
