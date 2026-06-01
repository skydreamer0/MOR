"""Monthly review → Excel workbook export.

Each region of the on-page review becomes its own sheet so the file is
self-contained and easy to share. Caller passes the already-built dataclasses
from the monthly_review_* modules; this module only handles formatting.
"""
from __future__ import annotations

from io import BytesIO

import pandas as pd

from src.backend.monthly_review import MonthlyReviewSummary
from src.backend.monthly_review_actions import ActionLists
from src.backend.monthly_review_customers import CustomerSummary
from src.backend.monthly_review_forecast_bias import ForecastBias
from src.backend.monthly_review_products import ProductSummary
from src.backend.monthly_review_trend import TrendSeries


def export_monthly_review(
    summary: MonthlyReviewSummary,
    *,
    actions: ActionLists | None = None,
    customers: CustomerSummary | None = None,
    products: ProductSummary | None = None,
    bias: ForecastBias | None = None,
    trend: TrendSeries | None = None,
) -> BytesIO:
    """Write all monthly review regions into one workbook. Returns BytesIO."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        _write_overview(writer, summary)
        if actions:
            _write_actions(writer, actions)
        if customers:
            _write_customers(writer, customers)
        if products:
            _write_products(writer, products)
        if bias:
            _write_bias(writer, bias)
        if trend:
            _write_trend(writer, trend)
        _write_detail(writer, summary)
    output.seek(0)
    return output


# ---------------------------------------------------------------------------
# Per-sheet writers
# ---------------------------------------------------------------------------

def _write_overview(writer: pd.ExcelWriter, s: MonthlyReviewSummary) -> None:
    fa = (s.forecast_amount_accuracy_total - 1) * 100 if s.forecast_amount_accuracy_total else None
    yoy = (s.yoy_amount_growth_total - 1) * 100 if s.yoy_amount_growth_total else None
    ba = s.budget_amount_achievement_total * 100 if s.budget_amount_achievement_total else None
    df = pd.DataFrame([
        {"項目": "月份",       "數值": f"{s.year}/{s.month:02d}"},
        {"項目": "結月於",     "數值": s.closed_at[:16]},
        {"項目": "實際金額",   "數值": round(s.actual_amount_total, 0)},
        {"項目": "預估金額",   "數值": round(s.forecast_amount_total, 0)},
        {"項目": "預算金額",   "數值": round(s.budget_amount_total, 0)},
        {"項目": "去年同期",   "數值": round(s.last_year_amount_total, 0)},
        {"項目": "預估準確率(%)", "數值": round(fa + 100, 1) if fa is not None else None},
        {"項目": "預算達成率(%)", "數值": round(ba, 1) if ba is not None else None},
        {"項目": "YoY 成長率(%)", "數值": round(yoy, 1) if yoy is not None else None},
    ])
    df.to_excel(writer, sheet_name="總覽", index=False)


def _write_actions(writer: pd.ExcelWriter, a: ActionLists) -> None:
    df = pd.concat([
        pd.DataFrame([{"清單": "失聯", "客戶": c.customer_name,
                       "金額(去年同期)": round(c.last_year_amount, 0),
                       "備註": ""} for c in a.lost]),
        pd.DataFrame([{"清單": "優先拜訪", "客戶": c.customer_name,
                       "金額(本月)": round(c.current_amount, 0),
                       "備註": f"YoY {(-c.yoy_drop)*100:.0f}%"} for c in a.priority]),
        pd.DataFrame([{"清單": "流失中", "客戶": c.customer_name,
                       "金額(本月)": round(c.trend[-1], 0),
                       "備註": " → ".join(f"{v:,.0f}" for v in c.trend)} for c in a.declining]),
        pd.DataFrame([{"清單": "新業務", "客戶": c.customer_name,
                       "金額(本月)": round(c.current_amount, 0),
                       "備註": ""} for c in a.new]),
    ], ignore_index=True)
    if df.empty:
        df = pd.DataFrame([{"清單": "(無)", "客戶": "", "金額": "", "備註": ""}])
    df.to_excel(writer, sheet_name="行動清單", index=False)


def _write_customers(writer: pd.ExcelWriter, cs: CustomerSummary) -> None:
    rows = []
    for r in cs.rows:
        yoy = round((r.yoy_growth - 1) * 100, 1) if r.yoy_growth is not None else None
        ba  = round(r.budget_achievement * 100, 1) if r.budget_achievement is not None else None
        rank_chg = (
            "新進" if r.last_year_rank is None
            else "—" if r.last_year_rank == r.rank
            else f"↑{r.last_year_rank - r.rank}" if r.last_year_rank > r.rank
            else f"↓{r.rank - r.last_year_rank}"
        )
        rows.append({
            "排名": r.rank, "客戶": r.customer_name,
            "實際金額": round(r.actual_amount, 0),
            "去年同期": round(r.last_year_amount, 0),
            "YoY(%)":   yoy,
            "預算":     round(r.budget_amount, 0),
            "達成率(%)": ba,
            "排名變化": rank_chg,
        })
    pd.DataFrame(rows).to_excel(writer, sheet_name="客戶總覽", index=False)


def _write_products(writer: pd.ExcelWriter, ps: ProductSummary) -> None:
    rows = []
    for r in ps.rows:
        yoy = round((r.yoy_growth - 1) * 100, 1) if r.yoy_growth is not None else None
        rows.append({
            "排名": r.rank,
            "品項": r.product_name or r.product_code,
            "數量": round(r.actual_quantity, 0),
            "金額": round(r.actual_amount, 0),
            "佔比(%)": round(r.revenue_share * 100, 1),
            "去年同期": round(r.last_year_amount, 0),
            "YoY(%)": yoy,
        })
    pd.DataFrame(rows).to_excel(writer, sheet_name="品項Top20", index=False)


def _write_bias(writer: pd.ExcelWriter, fb: ForecastBias) -> None:
    rows = []
    for r in fb.over_forecast:
        rows.append({"方向": "長期高估", "客戶": r.customer_name,
                     "品項": r.product_name or r.product_code,
                     "平均準確率(%)": round(r.avg_accuracy * 100, 1),
                     "觀察月數": r.months_observed})
    for r in fb.under_forecast:
        rows.append({"方向": "長期低估", "客戶": r.customer_name,
                     "品項": r.product_name or r.product_code,
                     "平均準確率(%)": round(r.avg_accuracy * 100, 1),
                     "觀察月數": r.months_observed})
    if not rows:
        rows = [{"方向": "(無偏誤)", "客戶": "", "品項": "", "平均準確率(%)": "", "觀察月數": ""}]
    pd.DataFrame(rows).to_excel(writer, sheet_name="預估偏誤", index=False)


def _write_trend(writer: pd.ExcelWriter, ts: TrendSeries) -> None:
    df = pd.DataFrame([
        {"月份": p.label,
         "實際": round(p.actual, 0),
         "預估": round(p.forecast, 0),
         "預算": round(p.budget, 0)}
        for p in ts.points
    ])
    df.to_excel(writer, sheet_name="趨勢12月", index=False)


def _write_detail(writer: pd.ExcelWriter, s: MonthlyReviewSummary) -> None:
    rows = []
    for r in s.rows:
        rows.append({
            "客戶": r.customer_name,
            "品項": r.product_name or r.product_code,
            "實際數量": round(r.actual_quantity, 0),
            "實際金額": round(r.actual_amount, 0),
            "預估金額": round(r.forecast_amount, 0),
            "預估GAP": round(r.forecast_amount_gap, 0),
            "去年同期": round(r.last_year_amount, 0),
            "YoY(%)": round((r.yoy_amount_growth - 1) * 100, 1) if r.yoy_amount_growth else None,
            "預算": round(r.budget_amount, 0),
            "達成率(%)": round(r.budget_amount_achievement * 100, 1) if r.budget_amount_achievement else None,
        })
    pd.DataFrame(rows).to_excel(writer, sheet_name="完整明細", index=False)
