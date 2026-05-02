from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ForecastConfig:
    detail_file: str = "業績明細202401-20260430-George.xlsx"
    detail_sheet: str = "業績明細"
    visible_row_limit: int = 300
    max_cycle_interval_days: int = 120
    required_columns: tuple[str, ...] = field(
        default=(
            "年",
            "月",
            "日",
            "客戶簡稱",
            "商品號",
            "商品簡稱",
            "銷+贈S量",
            "單價NT(淨)",
        )
    )
