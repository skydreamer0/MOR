"""Monthly review action lists."""
from __future__ import annotations

from dataclasses import dataclass

from src.backend.database import MORDatabase
from src.backend.monthly_review_data import MonthlyReviewDataReader


YOY_DROP_THRESHOLD = 0.20
PRIORITY_TOP_SHARE = 0.20
DECLINING_LOOKBACK_MONTHS = 3
ACTION_LIST_LIMIT = 10


@dataclass(frozen=True)
class LostCustomer:
    customer_name: str
    last_year_amount: float


@dataclass(frozen=True)
class PriorityVisitCustomer:
    customer_name: str
    current_amount: float
    last_year_amount: float
    yoy_drop: float


@dataclass(frozen=True)
class DecliningCustomer:
    customer_name: str
    trend: list[float]


@dataclass(frozen=True)
class NewCustomer:
    customer_name: str
    current_amount: float


@dataclass(frozen=True)
class ActionLists:
    lost: list[LostCustomer]
    priority: list[PriorityVisitCustomer]
    declining: list[DecliningCustomer]
    new: list[NewCustomer]


def build_action_lists(db: MORDatabase, year: int, month: int) -> ActionLists:
    reader = MonthlyReviewDataReader(db)
    current = reader.customer_amounts(year, month)
    last_year = reader.customer_amounts(year - 1, month)
    trends = _recent_customer_amounts(reader, year, month, DECLINING_LOOKBACK_MONTHS)

    return ActionLists(
        lost=_build_lost(current, last_year),
        priority=_build_priority(current, last_year),
        declining=_build_declining(trends),
        new=_build_new(current, last_year),
    )


def _recent_customer_amounts(
    reader: MonthlyReviewDataReader, year: int, month: int, lookback: int,
) -> dict[str, list[float]]:
    months = _last_n_months(year, month, lookback)
    trends: dict[str, list[float]] = {}
    for idx, (y, m) in enumerate(months):
        amounts = reader.customer_amounts(y, m)
        for customer, amount in amounts.items():
            trend = trends.setdefault(customer, [0.0] * lookback)
            trend[idx] = amount
    return trends


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


def _build_lost(current: dict[str, float], last_year: dict[str, float]) -> list[LostCustomer]:
    out = [
        LostCustomer(customer_name=customer, last_year_amount=amount)
        for customer, amount in last_year.items()
        if amount > 0 and current.get(customer, 0) <= 0
    ]
    out.sort(key=lambda row: -row.last_year_amount)
    return out[:ACTION_LIST_LIMIT]


def _build_priority(
    current: dict[str, float], last_year: dict[str, float],
) -> list[PriorityVisitCustomer]:
    if not current:
        return []
    top_cutoff = _percentile_floor(list(current.values()), 1.0 - PRIORITY_TOP_SHARE)
    candidates = []
    for customer, current_amount in current.items():
        last_year_amount = last_year.get(customer, 0.0)
        if current_amount < top_cutoff or last_year_amount <= 0:
            continue
        drop = (last_year_amount - current_amount) / last_year_amount
        if drop >= YOY_DROP_THRESHOLD:
            candidates.append(PriorityVisitCustomer(
                customer_name=customer,
                current_amount=current_amount,
                last_year_amount=last_year_amount,
                yoy_drop=drop,
            ))
    candidates.sort(key=lambda row: -row.yoy_drop)
    return candidates[:ACTION_LIST_LIMIT]


def _build_declining(trends: dict[str, list[float]]) -> list[DecliningCustomer]:
    out = []
    for customer, trend in trends.items():
        if len(trend) < 2:
            continue
        if any(trend[i] >= trend[i - 1] or trend[i] <= 0 for i in range(1, len(trend))):
            continue
        out.append(DecliningCustomer(customer_name=customer, trend=trend))
    out.sort(key=lambda row: row.trend[-1] - row.trend[0])
    return out[:ACTION_LIST_LIMIT]


def _build_new(current: dict[str, float], last_year: dict[str, float]) -> list[NewCustomer]:
    out = [
        NewCustomer(customer_name=customer, current_amount=amount)
        for customer, amount in current.items()
        if amount > 0 and last_year.get(customer, 0) <= 0
    ]
    out.sort(key=lambda row: -row.current_amount)
    return out[:ACTION_LIST_LIMIT]


def _percentile_floor(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = max(0, min(len(sorted_vals) - 1, int(len(sorted_vals) * q)))
    return sorted_vals[idx]
