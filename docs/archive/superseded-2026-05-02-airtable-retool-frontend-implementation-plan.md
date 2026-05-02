DO NOT USE FOR IMPLEMENTATION

# Airtable/Retool Frontend Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Convert MOR's current forecast review page into an Airtable-style Record Review + Retool-style internal tool experience while keeping Flask/Jinja, native export, and server-side forecast correctness.

**Architecture:** Keep the first implementation server-rendered. Jinja renders the forecast table and native form, static CSS owns the visual system, and one vanilla JavaScript controller owns filtering, edited/excluded state, validation hints, and derived totals. Add JSON presenter/API support only after the table UI is stable enough to need richer preview behavior.

**Tech Stack:** Flask, Jinja, pandas/openpyxl backend, vanilla JavaScript, plain CSS, pytest.

---

## Subagent Findings Summary

- **UI/template:** The current page already matches the right broad shape: dense review table, inline edits, status badges, sticky table header, fixed export bar. Main blocker is mojibake/readability in visible labels.
- **Frontend logic:** Keep Flask/Jinja + vanilla JS. Move toward `static/js/forecast-table.js` with pure calculation helpers and DOM rendering helpers.
- **Backend/data flow:** Existing domain modules are close, but richer grid behavior will eventually need JSON-safe serialization, column metadata, and preview endpoints.
- **Testing/risk:** Main risks are hidden/filtered rows losing edits, client/server total mismatch, and `error_message` being passed by `app.py` but not rendered by the template.

## Implementation Order

1. Stabilize current UI copy and error states.
2. Extract CSS/JS while preserving behavior.
3. Add Airtable/Retool table controls and row states.
4. Add backend presenter/API support only if the frontend needs richer state than native forms can handle.
5. Add browser/manual verification after tests pass.

---

## Task 1: Baseline Route And Template Characterization

**Files:**
- Modify: `tests/test_app.py`
- Read: `app.py`
- Read: `templates/index.html`

**Step 1: Write failing tests**

Add route/template tests for:

```python
def test_homepage_renders_error_message_for_missing_data_file(tmp_path):
    client = app.create_app({"TESTING": True, "DATA_BASE_PATH": tmp_path}).test_client()
    response = client.get("/")
    assert response.status_code == 200
    assert "無法產生預估" in response.get_data(as_text=True)


def test_homepage_renders_table_action_bar():
    client = app.create_app({"TESTING": True}).test_client()
    response = client.get("/")
    html = response.get_data(as_text=True)
    assert "forecast-tools" in html
    assert "狀態篩選" in html
    assert "搜尋客戶或商品" in html
```

**Step 2: Run tests to verify failure**

Run:

```powershell
D:\AI\python.exe -m pytest tests/test_app.py -q
```

Expected: fails because `error_message` is not rendered and table action bar does not exist.

**Step 3: Do not implement yet**

Keep the test red, then proceed to Task 2.

---

## Task 2: Repair UI Text And Error/Empty States

**Files:**
- Modify: `templates/index.html`
- Modify if needed: `DESIGN.md`
- Test: `tests/test_app.py`

**Step 1: Replace mojibake labels**

Use these visible labels:

| Area | Text |
| --- | --- |
| Header year | `年份` |
| Header month | `月份` |
| Header submit | `重新分析` |
| Metric month | `預估月份` |
| Metric shown | `目前顯示` |
| Metric auto rows | `自動預估列` |
| Metric total | `目前總額` |
| Status column | `狀態` |
| Auto badge | `本月可能跳單` |
| Not-due badge | `未到週期` |
| Bottom total | `預估總金額` |
| Export button | `匯出 Excel` |

**Step 2: Render errors and empty state**

Add an alert region above the metrics:

```html
{% if error_message %}
  <section class="alert" role="alert">{{ error_message }}</section>
{% endif %}
```

If no rows are available and there is no error, render a compact empty state:

```html
{% if not rows and not error_message %}
  <section class="empty-state">目前沒有符合條件的預估資料。</section>
{% endif %}
```

**Step 3: Run tests**

Run:

```powershell
D:\AI\python.exe -m pytest tests/test_app.py -q
```

Expected: error-state test passes; table action-bar test still fails.

---

## Task 3: Extract CSS Into A MOR Stylesheet

**Files:**
- Create: `static/css/mor.css`
- Modify: `templates/index.html`
- Test: `tests/test_app.py`

**Step 1: Move existing `<style>` content**

Move all inline CSS from `templates/index.html` into `static/css/mor.css`.

Add:

```html
<link rel="stylesheet" href="{{ url_for('static', filename='css/mor.css') }}">
```

**Step 2: Add design tokens**

Include tokens from `DESIGN.md`:

```css
--danger: #b42318;
--focus: #2563eb;
--surface-subtle: #f8fafc;
--success-bg: #e7f5ef;
--warning-bg: #fff4df;
```

**Step 3: Add alert/empty styles**

Add compact styles for `.alert` and `.empty-state`; keep them operational, not decorative.

**Step 4: Run tests**

Run:

```powershell
D:\AI\python.exe -m pytest tests/test_app.py -q
```

Expected: no route regression.

---

## Task 4: Extract JavaScript Into A Table Controller

**Files:**
- Create: `static/js/forecast-table.js`
- Modify: `templates/index.html`
- Test: `tests/test_app.py`

**Step 1: Add stable data attributes**

Each row should include:

```html
<tr
  data-row
  data-row-id="{{ row.row_id }}"
  data-status="{{ 'auto' if row.auto_in_month else 'not_due' }}"
  data-search="{{ row.customer }} {{ row.product_code }} {{ row.product_name }}"
  data-price="{{ row.latest_price }}"
  data-auto-qty="{{ row.forecast_quantity }}"
>
```

**Step 2: Move inline script**

Create `static/js/forecast-table.js` with:

```js
const formatter = new Intl.NumberFormat("zh-TW", { maximumFractionDigits: 0 });

function readRowState(row) {
  const manualInput = row.querySelector("[data-manual]");
  const excludedInput = row.querySelector("[data-exclude]");
  return {
    row,
    rowId: row.dataset.rowId,
    status: row.dataset.status,
    price: Number(row.dataset.price || 0),
    autoQuantity: Number(row.dataset.autoQty || 0),
    manualValue: manualInput.value,
    excluded: excludedInput.checked,
  };
}
```

Add helpers:

- `effectiveQuantity(state)`
- `calculateAmount(state)`
- `renderRow(state)`
- `recalculate()`
- `bindForecastTable()`

**Step 3: Load the script**

At the bottom of `templates/index.html`:

```html
<script src="{{ url_for('static', filename='js/forecast-table.js') }}"></script>
```

**Step 4: Run tests**

Run:

```powershell
D:\AI\python.exe -m pytest tests/test_app.py -q
```

Expected: no route regression and script tag renders.

---

## Task 5: Add Airtable/Retool Table Action Bar

**Files:**
- Modify: `templates/index.html`
- Modify: `static/css/mor.css`
- Modify: `static/js/forecast-table.js`
- Test: `tests/test_app.py`

**Step 1: Add action bar markup**

Add above `.table-wrap`:

```html
<div class="forecast-tools" aria-label="表格工具">
  <label>
    搜尋客戶或商品
    <input type="search" data-filter-search placeholder="輸入客戶、商品號或商品名稱">
  </label>
  <label>
    狀態篩選
    <select data-filter-status>
      <option value="all">全部</option>
      <option value="auto">本月可能跳單</option>
      <option value="not_due">未到週期</option>
      <option value="edited">已人工調整</option>
      <option value="excluded">已排除</option>
    </select>
  </label>
  <div class="tool-counts">
    <span>顯示 <strong data-visible-count>{{ shown_count }}</strong> 筆</span>
    <span>已調整 <strong data-edited-count>0</strong> 筆</span>
    <span>已排除 <strong data-excluded-count>0</strong> 筆</span>
  </div>
</div>
```

**Step 2: Implement filtering**

In `forecast-table.js`, add:

- Search by `data-search`.
- Status filter by `data-status`, edited state, and excluded state.
- Keep filtered rows mounted in the DOM; use `hidden` or a CSS class to hide them.

**Step 3: Clarify totals**

Keep `grand-total` as total for all mounted rows, not only visible filtered rows. Add label text if needed:

```text
預估總金額
```

Do not make filtered totals unless the UI explicitly labels them.

**Step 4: Run tests**

Run:

```powershell
D:\AI\python.exe -m pytest tests/test_app.py -q
```

Expected: table action-bar test passes.

---

## Task 6: Add Row Review States

**Files:**
- Modify: `templates/index.html`
- Modify: `static/css/mor.css`
- Modify: `static/js/forecast-table.js`

**Step 1: Add row classes from JS**

`renderRow(state)` should toggle:

- `.excluded`
- `.edited`
- `.invalid`

**Step 2: Add accessible row feedback**

Manual quantity input should get:

```html
aria-label="人工預估數量"
```

Exclusion checkbox should get:

```html
aria-label="排除此列"
```

**Step 3: Add validation**

Before export:

- Block negative manual quantity.
- Block non-numeric manual quantity.
- Mark invalid input and focus it.
- Keep server-side validation as final authority.

**Step 4: Run tests**

Run:

```powershell
D:\AI\python.exe -m pytest -q
```

Expected: all Python tests pass.

---

## Task 7: Backend Presenter And Preview API Planning Gate

**Files:**
- Create later only if needed: `web/forecast_presenter.py`
- Create later only if needed: `tests/test_forecast_presenter.py`
- Modify later only if needed: `app.py`

**Step 1: Do not add API endpoints in the first UI pass**

Keep native form export until filtering and row states are proven.

**Step 2: Add presenter only when needed**

If the UI needs full-row JSON bootstrapping or async preview, add:

```python
def serialize_summary(summary: ForecastSummary) -> dict:
    ...

def column_schema() -> list[dict]:
    ...
```

Dates must be ISO strings, not Python `date` objects.

**Step 3: Optional endpoints**

Only after presenter tests pass:

- `GET /api/forecast`
- `POST /api/forecast/preview`

**Step 4: Tests**

Add tests for:

- JSON-safe dates.
- Column schema labels and alignment.
- Preview adjusted totals.
- Structured `400` validation errors.

---

## Task 8: Visual And Workflow Verification

**Files:**
- No required source changes unless verification finds defects.

**Step 1: Run backend tests**

```powershell
D:\AI\python.exe -m pytest -q
```

Expected: all tests pass.

**Step 2: Run the app**

```powershell
D:\AI\python.exe app.py
```

Open:

```text
http://127.0.0.1:5000/
```

**Step 3: Manual browser checks**

Verify:

- Chinese labels render correctly.
- Search filters rows without losing input values.
- Status filter works.
- Manual quantity updates row amount and grand total.
- Excluding a row mutes it and sets amount to 0.
- Edited/excluded counters update.
- Export still downloads Excel.
- Invalid manual quantity is blocked client-side and rejected server-side.

**Step 4: Documentation update**

If the UI behavior changes materially, update:

- `DESIGN.md`
- `docs/design/frontend-design.md`
- `docs/design/frontend-logic-architecture.md`

---


## Execution Status (2026-05-02)

- ✅ Task 1–6 completed in current workspace (baseline tests, UTF-8 labels, error/empty state, static CSS/JS extraction, Airtable/Retool action bar, row review state + client validation).
- ✅ Current Python test suite passes with `PYTHONPATH=. pytest -q`.
- ⏸️ Task 7 remains gated by roadmap decision: keep presenter/API optional until native form workflow is proven insufficient.
- 🔜 Next execution focus: Task 8 browser verification + targeted docs sync if new UX behavior is introduced.

## Out Of Scope For This Plan

- React, Next.js, shadcn/ui, or TanStack Table migration.
- Saved forecast drafts.
- Login/authentication.
- Database persistence.
- Charts or dashboard pages.
- Replacing Excel export with client-side export.

## Recommended Commit Slices

1. `test: characterize forecast review page`
2. `fix: repair MOR forecast review labels`
3. `refactor: extract MOR frontend assets`
4. `feat: add forecast table filters and row states`
5. `docs: update MOR frontend implementation notes`

