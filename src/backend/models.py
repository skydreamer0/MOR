from __future__ import annotations

from dataclasses import dataclass, replace
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
    forecast_quantity: float
    manual_quantity: float | None
    effective_quantity: float
    estimated_amount: float
    forecast_basis: str
    excluded: bool = False

    def with_adjustment(self, manual_quantity: float | None, excluded: bool) -> "ForecastRow":
        effective_quantity = float(manual_quantity) if manual_quantity is not None else float(self.forecast_quantity)
        estimated_amount = 0.0 if excluded else effective_quantity * float(self.latest_price)
        return replace(
            self,
            manual_quantity=manual_quantity,
            effective_quantity=effective_quantity,
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
            "forecast_quantity": self.forecast_quantity,
            "manual_quantity": self.manual_quantity,
            "effective_quantity": self.effective_quantity,
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
