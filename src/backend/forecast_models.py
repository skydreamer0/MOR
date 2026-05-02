from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, timedelta


@dataclass(frozen=True)
class ForecastTarget:
    year: int
    month: int

    @property
    def start(self) -> date:
        return date(self.year, self.month, 1)

    @property
    def end(self) -> date:
        if self.month == 12:
            return date(self.year + 1, 1, 1) - timedelta(days=1)
        return date(self.year, self.month + 1, 1) - timedelta(days=1)


@dataclass(frozen=True)
class ForecastOptions:
    include_all: bool = False
    max_cycle_interval_days: int = 120
    excluded_item_ids: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class ForecastRow:
    row_id: str
    customer: str
    product_code: str
    product_name: str
    latest_order_date: date
    cycle_days: int | None
    next_order_date: date | None
    auto_in_month: bool
    last_year_same_month_qty: float
    this_year_same_month_qty: float
    latest_price: float
    system_forecast: float
    manual_adjustment: float | None
    final_forecast: float
    adjustment_reason: str | None = None
    budget_quantity: float = 0.0
    estimated_amount: float
    forecast_basis: str
    excluded: bool = False

    def with_adjustment(self, manual_adjustment: float | None, excluded: bool) -> "ForecastRow":
        final_forecast = float(manual_adjustment) if manual_adjustment is not None else float(self.system_forecast)
        estimated_amount = 0.0 if excluded else final_forecast * float(self.latest_price)
        return replace(
            self,
            manual_adjustment=manual_adjustment,
            final_forecast=final_forecast,
            estimated_amount=estimated_amount,
            excluded=excluded,
        )

    def to_dict(self) -> dict:
        return {
            "row_id": self.row_id,
            "customer": self.customer,
            "product_code": self.product_code,
            "product_name": self.product_name,
            "latest_order_date": self.latest_order_date,
            "cycle_days": self.cycle_days,
            "next_order_date": self.next_order_date,
            "auto_in_month": self.auto_in_month,
            "last_year_same_month_qty": self.last_year_same_month_qty,
            "this_year_same_month_qty": self.this_year_same_month_qty,
            "latest_price": self.latest_price,
            "system_forecast": self.system_forecast,
            "manual_adjustment": self.manual_adjustment,
            "final_forecast": self.final_forecast,
            "adjustment_reason": self.adjustment_reason,
            "budget_quantity": self.budget_quantity,
            "estimated_amount": self.estimated_amount,
            "forecast_basis": self.forecast_basis,
            "excluded": self.excluded,
        }


@dataclass(frozen=True)
class ForecastSummary:
    year: int
    month: int
    rows: list[ForecastRow]
    total: float

    @property
    def row_count(self) -> int:
        return len(self.rows)

    @property
    def auto_row_count(self) -> int:
        return sum(1 for row in self.rows if row.auto_in_month)
