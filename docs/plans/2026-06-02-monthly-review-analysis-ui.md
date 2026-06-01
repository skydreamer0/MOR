# Monthly Review Analysis UI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve `/monthly-review` into a compact monthly business review workspace with sales actions, boss-report summary, forecast-model review, clearer KPI semantics, and filterable details.

**Architecture:** Reuse the existing Flask route and monthly-review backend services. Keep changes in Jinja partials, page-specific CSS, vanilla JavaScript, and route smoke tests; do not add dependencies or persistence.

**Tech Stack:** Flask, Jinja templates, vanilla JavaScript, CSS in `static/css/mor.css`, pytest route/UI assertions.

---

### Task 1: Add UI Assertions For The New Workbench Shape

**Files:**
- Modify: `tests/test_app.py`

**Step 1: Write the failing test**

Add assertions to the existing monthly-review page test so rendered HTML must include:

```python
assert "本月優先處理" in html
assert "review-priority-board" in html
assert "老闆報告摘要" in html
assert "預估模型檢討" in html
assert "review-detail-filter" in html
assert "review-detail-search" in html
```

**Step 2: Run test to verify it fails**

Run: `D:\AI\python.exe -m pytest tests/test_app.py -q`

Expected: FAIL because the new section and controls are missing.

### Task 2: Rework Summary, Priority Board, Report Summary, And Model Review

**Files:**
- Modify: `templates/_monthly_review_summary.html`
- Modify: `templates/_monthly_review_insights.html`
- Modify: `templates/_monthly_review_macros.html`

**Step 1: Implement summary cards**

Update the top cards to show:

- 實際金額 with row count
- 預算達成 with budget amount
- YoY with last-year amount
- 預估準確率 with forecast amount

Use page-specific classes for risk coloring instead of the global `.rising/.falling` convention where monthly-review meaning differs.

**Step 2: Implement priority board**

Add a `review-priority-board` section at the top of `_monthly_review_insights.html`.

Use existing template data:

- `action_lists.lost`
- `action_lists.priority`
- `action_lists.declining`
- `summary.rows` sorted by `yoy_amount_delta`, `budget_amount_delta`, and `forecast_amount_gap`

Keep it compact and cap each list to a small number of rows.

**Step 3: Implement boss-report summary**

Add a `老闆報告摘要` section that shows:

- A concise factual monthly conclusion.
- Actual amount, budget achievement, YoY, forecast accuracy.
- Top growth and top risk rows by amount impact.

Use existing `summary.rows`; no new service is required for the first implementation.

**Step 4: Implement forecast-model review**

Add a `預估模型檢討` section that groups:

- `forecast_bias.over_forecast`
- `forecast_bias.under_forecast`
- current-month rows with forecast amount accuracy outside 85%-115%

Use labels that tell next-cycle action: 下修, 上修, 重新確認.

### Task 3: Upgrade Detail Filtering

**Files:**
- Modify: `templates/_monthly_review_detail.html`
- Modify: `static/js/monthly-review.js`

**Step 1: Add controls and data attributes**

Add:

```html
<input id="review-detail-search" ...>
<select id="review-detail-filter" ...>
<span id="review-detail-count">...</span>
```

Each `<tr>` should include `data-search`, `data-anomaly`, `data-yoy-risk`, `data-budget-risk`, and `data-forecast-risk`.

**Step 2: Implement JS filter behavior**

Update `monthly-review.js` so search and select filters combine with the existing anomaly behavior. Keep all behavior local to the page.

### Task 4: Add Monthly Review Styling

**Files:**
- Modify: `static/css/mor.css`

**Step 1: Style the workbench**

Add page-specific styles for:

- `review-metric-card--risk`
- `review-metric-card--ok`
- `review-priority-board`
- `review-priority-list`
- `review-priority-tag`
- detail filter controls and visible count

Keep spacing in existing tokens and preserve table density.

### Task 5: Verify

**Files:**
- Test: route/UI tests

**Step 1: Run focused tests**

Run: `D:\AI\python.exe -m pytest tests/test_app.py tests/test_monthly_review.py tests/test_monthly_review_actions.py tests/test_monthly_review_chart.py -q`

**Step 2: Run syntax check**

Run: `D:\AI\python.exe -m py_compile app.py src\backend\app.py`

**Step 3: Review diff**

Run: `git diff -- templates/_monthly_review_summary.html templates/_monthly_review_insights.html templates/_monthly_review_detail.html templates/_monthly_review_macros.html static/css/mor.css static/js/monthly-review.js tests/test_app.py docs/plans/2026-06-02-monthly-review-analysis-ui-design.md docs/plans/2026-06-02-monthly-review-analysis-ui.md`
