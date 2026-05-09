"""
analytics.py — shared analytics computation layer

Provides AnalyticsSlice (the common data structure) and helpers for building
slices from raw sales + budget data.  Used by:

  • forecast sidebar  — data embedded in <tr data-*> attributes at render time
  • future dashboard  — API endpoints aggregate across customers / products
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import pandas as pd

__all__ = [
    "AnalyticsSlice",
    "build_slice_from_df",
    "build_all_slices",
]

EntityType = Literal["total", "customer", "product", "row"]

_ZERO_12: list[float] = [0.0] * 12


# ── Core data structure ───────────────────────────────────────────────────────

@dataclass
class AnalyticsSlice:
    """All analytics for one dimension slice (total / customer / product / row)."""

    entity_id: str
    entity_label: str
    entity_type: EntityType
    target_year: int
    target_month: int                    # 1-based forecast month

    ly_monthly: list[float]              # [12] Jan=index 0, last year quantity
    ty_monthly: list[float]              # [12] confirmed actual quantity; future months = 0
    budget_monthly: list[float]          # [12] budget target quantities per month
    # forecast quantity for target_month only; zeros elsewhere
    forecast_monthly: list[float] = field(default_factory=lambda: [0.0] * 12)
    # amount (qty × price) tracks — parallel to quantity tracks above
    ly_monthly_amount: list[float] = field(default_factory=lambda: [0.0] * 12)
    ty_monthly_amount: list[float] = field(default_factory=lambda: [0.0] * 12)
    budget_monthly_amount: list[float] = field(default_factory=lambda: [0.0] * 12)
    forecast_amount: float = 0.0

    # ── Last month with confirmed actual data ─────────────────────────────────

    @property
    def last_actual_month(self) -> int:
        """1-based index of the latest month that has non-zero actual data (0 if none)."""
        for i in range(11, -1, -1):
            if self.ty_monthly[i] > 0:
                return i + 1
        return 0

    # ── YTD cumulative (1月 → last_actual_month, confirmed actuals only) ──────

    @property
    def ytd_ly(self) -> float:
        return _sum(self.ly_monthly[: self.last_actual_month])

    @property
    def ytd_ty(self) -> float:
        return _sum(self.ty_monthly[: self.last_actual_month])

    @property
    def ytd_budget(self) -> float:
        return _sum(self.budget_monthly[: self.last_actual_month])

    @property
    def ytd_ly_amount(self) -> float:
        return _sum(self.ly_monthly_amount[: self.last_actual_month])

    @property
    def ytd_ty_amount(self) -> float:
        return _sum(self.ty_monthly_amount[: self.last_actual_month])

    @property
    def ytd_budget_amount(self) -> float:
        return _sum(self.budget_monthly_amount[: self.last_actual_month])

    @property
    def ytd_gap_vs_ly(self) -> float:
        """Today YTD minus last-year same-period YTD."""
        return self.ytd_ty - self.ytd_ly

    @property
    def ytd_rate_vs_ly(self) -> float:
        """This-year YTD as % of last-year YTD."""
        return (self.ytd_ty / self.ytd_ly * 100) if self.ytd_ly > 0 else 0.0

    @property
    def ytd_budget_rate(self) -> float:
        """This-year YTD as % of budget YTD."""
        return (self.ytd_ty / self.ytd_budget * 100) if self.ytd_budget > 0 else 0.0

    # ── Moving averages (months before target_month) ──────────────────────────

    @property
    def ma3(self) -> float:
        """3-month moving average of this year ending before target month."""
        return _avg(self.ty_monthly[max(0, self.target_month - 4): self.target_month - 1])

    @property
    def ma6(self) -> float:
        return _avg(self.ty_monthly[max(0, self.target_month - 7): self.target_month - 1])

    # ── Trend direction ───────────────────────────────────────────────────────

    @property
    def trend_direction(self) -> Literal["up", "flat", "down"]:
        """Compare most-recent 3M avg vs the 3M before that."""
        recent = _avg(self.ty_monthly[max(0, self.target_month - 4): self.target_month - 1])
        prev   = _avg(self.ty_monthly[max(0, self.target_month - 7): self.target_month - 4])
        if prev == 0:
            return "flat"
        ratio = recent / prev
        if ratio >= 1.05:
            return "up"
        if ratio <= 0.95:
            return "down"
        return "flat"

    # ── Serialization (for API responses and data-* embedding) ───────────────

    def to_dict(self) -> dict:
        return {
            "entity_id":            self.entity_id,
            "entity_label":         self.entity_label,
            "entity_type":          self.entity_type,
            "target_year":          self.target_year,
            "target_month":         self.target_month,
            "last_actual_month":    self.last_actual_month,
            "ly_monthly":           self.ly_monthly,
            "ty_monthly":           self.ty_monthly,
            "budget_monthly":       self.budget_monthly,
            "forecast_monthly":     self.forecast_monthly,
            "ly_monthly_amount":    self.ly_monthly_amount,
            "ty_monthly_amount":    self.ty_monthly_amount,
            "budget_monthly_amount": self.budget_monthly_amount,
            "forecast_amount":      round(self.forecast_amount, 2),
            # derived quantity-based (for trend chart + sparklines)
            "ytd_ly":          round(self.ytd_ly, 2),
            "ytd_ty":          round(self.ytd_ty, 2),
            "ytd_budget":      round(self.ytd_budget, 2),
            "ytd_gap_vs_ly":   round(self.ytd_gap_vs_ly, 2),
            "ytd_rate_vs_ly":  round(self.ytd_rate_vs_ly, 1),
            "ytd_budget_rate": round(self.ytd_budget_rate, 1),
            "ma3":             round(self.ma3, 2),
            "ma6":             round(self.ma6, 2),
            "trend_direction": self.trend_direction,
            # derived amount-based (for customer/product analytics tables)
            "ytd_ly_amount":     round(self.ytd_ly_amount, 2),
            "ytd_ty_amount":     round(self.ytd_ty_amount, 2),
            "ytd_budget_amount": round(self.ytd_budget_amount, 2),
        }


# ── Slice builders ────────────────────────────────────────────────────────────

def build_slice_from_df(
    sales_df: pd.DataFrame,
    budget_rows: list[dict],          # rows from budget_targets for all months of year
    target_year: int,
    target_month: int,
    entity_type: EntityType,
    entity_id: str,
    entity_label: str,
) -> AnalyticsSlice:
    """
    Build one AnalyticsSlice from a (pre-filtered) sales DataFrame.
    budget_rows: list of dicts with keys year, month, target_quantity.
    """
    ly_monthly = [
        _month_qty(sales_df, target_year - 1, m) for m in range(1, 13)
    ]
    ty_monthly = [
        _month_qty(sales_df, target_year, m) for m in range(1, 13)
    ]
    budget_by_month: dict[int, float] = {}
    for br in budget_rows:
        if br.get("year") == target_year:
            budget_by_month[int(br["month"])] = float(br.get("target_quantity") or 0)
    budget_monthly = [budget_by_month.get(m, 0.0) for m in range(1, 13)]

    return AnalyticsSlice(
        entity_id=entity_id,
        entity_label=entity_label,
        entity_type=entity_type,
        target_year=target_year,
        target_month=target_month,
        ly_monthly=ly_monthly,
        ty_monthly=ty_monthly,
        budget_monthly=budget_monthly,
    )


def build_all_slices(
    sales_df: pd.DataFrame,
    budget_df: pd.DataFrame,           # full budget_targets as DataFrame
    target_year: int,
    target_month: int,
    entity_type: EntityType,
) -> list[AnalyticsSlice]:
    """
    Build one AnalyticsSlice per unique entity of the given type.
    entity_type = "total"    → one slice for the whole company
    entity_type = "customer" → one slice per customer
    entity_type = "product"  → one slice per product_code
    """
    qty_col    = "銷+贈S量"
    year_col   = "年"
    month_col  = "月"
    cust_col   = "客戶簡稱"
    prod_col   = "商品號"

    if entity_type == "total":
        bud_rows = budget_df.to_dict("records") if not budget_df.empty else []
        return [build_slice_from_df(
            sales_df, bud_rows, target_year, target_month,
            "total", "total", "全公司",
        )]

    if entity_type == "customer":
        results = []
        for customer, grp in sales_df.groupby(cust_col, dropna=False):
            cid = str(customer)
            bud_rows = (
                budget_df[budget_df["customer_name"] == cid].to_dict("records")
                if not budget_df.empty else []
            )
            results.append(build_slice_from_df(
                grp, bud_rows, target_year, target_month,
                "customer", cid, cid,
            ))
        return results

    if entity_type == "product":
        results = []
        for product_code, grp in sales_df.groupby(prod_col, dropna=False):
            pid = str(product_code)
            bud_rows = (
                budget_df[budget_df["product_code"] == pid].to_dict("records")
                if not budget_df.empty else []
            )
            # Use most recent product name from sales data
            name_col = "商品簡稱"
            label = pid
            if name_col in grp.columns:
                names = grp[name_col].dropna()
                if not names.empty:
                    label = str(names.iloc[-1])
            results.append(build_slice_from_df(
                grp, bud_rows, target_year, target_month,
                "product", pid, label,
            ))
        return results

    return []


# ── Private helpers ───────────────────────────────────────────────────────────

def _month_qty(df: pd.DataFrame, year: int, month: int) -> float:
    if df.empty:
        return 0.0
    mask = (df["年"] == year) & (df["月"] == month)
    return float(df.loc[mask, "銷+贈S量"].sum())


def _sum(values: list[float]) -> float:
    return sum(v for v in values if v)


def _avg(values: list[float]) -> float:
    nonzero = [v for v in values if v and v > 0]
    return sum(nonzero) / len(nonzero) if nonzero else 0.0
