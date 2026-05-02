from __future__ import annotations

from io import BytesIO

import pandas as pd

from forecast_models import ForecastRow, ForecastSummary


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
        "客戶": row.customer,
        "商品號": row.product_code,
        "商品": row.product_name,
        "最近叫貨日": row.latest_order_date,
        "平均跳單週期": row.cycle_days,
        "推估下次叫貨日": row.next_order_date,
        "去年同月數量": row.last_year_same_month_qty,
        "今年同月數量": row.this_year_same_month_qty,
        "最近單價": row.latest_price,
        "系統預估數量": row.forecast_quantity,
        "人工預估數量": row.manual_quantity,
        "有效預估數量": row.effective_quantity,
        "預估金額": row.estimated_amount,
        "預估依據": row.forecast_basis,
        "是否排除": "是" if row.excluded else "否",
    }
