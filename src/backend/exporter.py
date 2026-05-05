from __future__ import annotations

from io import BytesIO

import pandas as pd

from src.backend.forecast_models import ForecastRow, ForecastSummary


def export_forecast(summary: ForecastSummary) -> BytesIO:
    output = BytesIO()
    export_rows = [_format_export_row(row) for row in summary.rows]

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame(
            [
                {"項目": "預估月份", "數值": f"{summary.year}/{summary.month:02d}"},
                {"項目": "預估總金額", "數值": summary.total},
                {"項目": "列入預估品項數", "數值": sum(1 for row in summary.rows if not row.excluded)},
                {"項目": "排除品項數", "數值": sum(1 for row in summary.rows if row.excluded)},
            ]
        ).to_excel(writer, sheet_name="預估總覽", index=False)
        pd.DataFrame(export_rows).to_excel(writer, sheet_name="預估明細", index=False)
        pd.DataFrame([row for row in export_rows if row["是否排除"] == "是"]).to_excel(
            writer, sheet_name="排除明細", index=False
        )

    output.seek(0)
    return output


def _format_export_row(row: ForecastRow) -> dict:
    return {
        "醫院 (客戶)": row.customer,
        "品項名稱": row.product_name,
        "去年同期量": row.last_year_same_month_qty,
        "實際數量 (本月)": row.this_year_same_month_qty,
        "系統預估": row.system_forecast,
        "人工調整": row.manual_adjustment,
        "最終預估": row.final_forecast,
        "調整原因": row.adjustment_reason,
        "預估金額": row.estimated_amount,
        "是否排除": "是" if row.excluded else "否",
    }
