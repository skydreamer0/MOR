from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class DataIssue:
    level: str
    message: str


def validate(df: pd.DataFrame, budget_df: pd.DataFrame | None) -> list[DataIssue]:
    issues: list[DataIssue] = []
    if budget_df is None or budget_df.empty:
        issues.append(DataIssue("warning", "尚未載入預算檔案，達成率計算將略過"))

    if "單價NT(淨)" in df.columns:
        zero_price_count = int((df["單價NT(淨)"] == 0).sum())
        if zero_price_count:
            issues.append(_zero_price_issue(zero_price_count))

    return issues


def validate_health(health) -> list[DataIssue]:
    issues: list[DataIssue] = []
    if health is None:
        return issues

    if health.zero_price_row_count > 0:
        issues.append(_zero_price_issue(health.zero_price_row_count))
    return issues


def validate_budget_coverage(
    sales_product_codes: "set[str]",
    budget_product_codes: "set[str]",
) -> list[DataIssue]:
    """Check for budget products with no matching sales history."""
    unmapped = budget_product_codes - sales_product_codes
    if unmapped:
        return [DataIssue(
            "warning",
            f"有 {len(unmapped)} 個預算品項在業績明細中無對應紀錄，GAP 計算可能不完整",
        )]
    return []


def _zero_price_issue(count: int) -> DataIssue:
    return DataIssue("warning", f"有 {count} 筆單價為 0，金額估算可能不準確")
