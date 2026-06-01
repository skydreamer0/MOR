# Monthly Review Analysis UI Design

Date: 2026-06-02

## Goal

Turn `/monthly-review` from a stacked report into a sales monthly-review workspace. The page should help a salesperson, sales lead, and monthly boss-review meeting answer five questions in order:

1. 本月結果好不好？
2. 下一步要追誰、為什麼、差多少？
3. 跟老闆報告時，哪些數字能支撐本月結論？
4. 預估模型哪裡長期高估或低估？
5. 需要下鑽時，哪些客戶、品項、預估偏誤造成結果？

## Chosen Direction

Use **A + B + C in one hierarchy**:

- A: 業務行動工作台 is the first screen.
- B: 主管月會報告 becomes a compact report-summary band below the action board.
- C: 預估模型檢討 becomes a focused model-review section, not just another raw table.

The first screen remains compact and operational. It keeps the existing MOR design logic: table-first, dense, neutral surfaces, right-aligned numbers, clear status colors, no marketing hero, no decorative layout.

## Page Structure

### 1. Month Toolbar

Keep the current month picker, export, and print actions.

### 2. 本月結論

Replace the current flat metric cards with compact review cards:

- 實際金額
- 預算達成
- YoY
- 預估準確率

Each card should expose both the main value and the business comparison. For this page, negative YoY and budget misses are risk signals and should use risk styling even if other pages use the Taiwanese market convention of 漲紅跌綠.

### 3. 本月優先處理

Add this section before trend charts and broad tables. It should combine existing backend data into a single action-first view:

- 失聯名單
- 優先拜訪
- 流失中
- 低於去年同期
- 低於預算
- 預估失準

Rows should show:

- 客戶
- 品項 when row-level
- reason label
- amount or amount gap
- small context such as YoY %, budget achievement %, or forecast accuracy %

No new persistence is needed. Reuse existing `summary.rows`, `action_lists`, and `forecast_bias`.

### 4. 老闆報告摘要

Add a compact report band for the monthly meeting. It should be readable without digging through the full table:

- 本月一句話結論: derived from budget achievement, YoY, and forecast accuracy.
- 成績亮點: top growing customers/products by amount impact.
- 風險缺口: largest YoY and budget misses by amount impact.
- 報告用數字: actual amount, budget achievement, YoY, forecast accuracy.

This section should stay factual and concise. It is not a slide deck and should not become a marketing-style hero.

### 5. 趨勢與原因

Keep the 12-month chart and forecast-bias panels. They explain the action list rather than competing with it.

### 6. 預估模型檢討

Make forecast-bias and forecast-accuracy information easier to interpret:

- 長期高估: next forecast should be reduced.
- 長期低估: next forecast should be raised.
- 本月失準: rows with forecast accuracy outside the review band.

This should help improve the next forecast cycle, not only explain the closed month.

### 7. 客戶與品項分析

Keep customer Top and product Top tables. Add stronger amount deltas where useful so the user can prioritize by business impact instead of percentages alone.

### 8. 完整明細

Upgrade the detail table from raw dump to filterable work table:

- Search customer/product text.
- Filter anomaly type:
  - 全部
  - 只看異常
  - YoY 下滑
  - 低於預算
  - 預估失準
- Show visible row count.
- Default rows should carry enough `data-*` attributes for client-side filtering.

## Acceptance Criteria

1. `/monthly-review` first screen includes a clearly labeled `本月優先處理` section when summary data exists.
2. Page includes a clearly labeled `老闆報告摘要` section for monthly review meetings.
3. Page includes a clearly labeled `預估模型檢討` section for high/low forecast bias and current-month forecast misses.
4. KPI cards use monthly-review-specific risk semantics: YoY below 100% and budget below target are visually risky.
5. Priority rows show absolute money impact where available, not only percentages.
6. Detail table supports text search and anomaly-type filtering without a frontend framework.
7. Layout remains compact, table-first, and consistent with `DESIGN.md`.
8. Export behavior is unchanged.
9. Existing monthly-review route tests still pass, with focused UI assertions added for the new structure.

## Files Expected To Change

- `templates/_monthly_review_summary.html`
- `templates/_monthly_review_insights.html`
- `templates/_monthly_review_detail.html`
- `templates/_monthly_review_macros.html`
- `static/css/mor.css`
- `static/js/monthly-review.js`
- `tests/test_app.py`
