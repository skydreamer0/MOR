# MOR Roadmap

## Current Focus

Make MOR a compact multi-page operating tool:

1. Dashboard for quick business overview.
2. Product drop monitor for daily risk review.
3. Forecast adjustment page for manual overrides and export.
4. Settings and data checks page for item rules and source-data health.

## Small Task Queue

1. Finish multi-page UI verification in browser.
2. Improve data health checks for missing budget mappings.
3. Add customer view page after monitor rules stabilize.
4. Add product view page after customer view is useful.

---

## Frontend Improvement Plan

Staged fixes identified from architecture review on 2026-05-09. Do not start a later phase before completing the current one.

### Phase 1 — Correctness (Bug Risk) `priority: high`

These have actual incorrect behaviour under normal usage.

- [x] **Unify row visibility into one mechanism.**
  Currently three competing systems exist in the forecast table:
  `row.hidden` (search/status filter in `recalculate`),
  `tr.style.display` (customer dropdown in `filterRows`), and
  `.forecast-table__row--collapsed` (anomaly view toggle in `applyViewMode`).
  They can layer in unpredictable order; total and count displays show wrong values when more than one filter is active simultaneously.
  Fix: fold `filterRows` into `recalculate` state using a `data-customer` dataset check, and fold `applyViewMode` into the same visible-flag logic, so a single `row.hidden = !visible` pass controls everything.

- [x] **Replace positional `nth-child` column-group borders with class selectors.**
  `mor.css` lines 921–926 use `tbody td:nth-child(9)` and `tbody td:nth-child(13)` for group dividers.
  Adding or removing any column silently shifts the borders to the wrong columns.
  Fix: add `col-group-start` class to the relevant `<td>` cells in `_forecast_row.html` (already applied to `<th>` in the header) and remove the `nth-child` rules.

### Phase 2 — Consistency (Design System Integrity) `priority: medium`

These do not break behaviour but will cause agent and dev errors over time.

- [x] **Sync DESIGN.md token values with `mor.css`.**
  `DESIGN.md` lists `--ink: #16202a` but `mor.css` uses `#0f172a`. Several tokens in the
  "Recommended additions" block have since been implemented in CSS but the doc still marks them as suggestions.
  Fix: update `DESIGN.md` Section 2 to reflect the actual token values in `mor.css`; remove the split between "current" and "recommended" since all tokens now exist.

- [x] **Move hardcoded hover colour into design token.**
  `mor.css` line 511: `background-color: #eef6ff` (blue tint) is the only hardcoded colour
  outside the token system. It conflicts with the teal accent identity.
  Fix: add `--row-hover: #eef6ff` (or convert to an accent-based tint) to `:root` and reference it in the hover rule.

### Phase 3 — Maintainability `priority: low`

Clean-up that makes future changes safer and faster.

- [x] **Unify customer dropdown with the main filter path.**
  The customer `<select>` fires `filterRows()` which bypasses `recalculate()`.
  After Phase 1 is done, fold the customer value into the unified visibility check so search,
  status, customer, and anomaly-only all go through one pass.

- [x] **Extract `<thead>` into a shared partial.**
  Created `templates/_forecast_thead.html`; both main and discontinued tables now include it.
  Also fixed a latent bug: the discontinued thead was missing `col-group-start` on 最後預估 (Phase 1
  replace_all missed it due to different indentation depth).

- [x] **Audit HTMX usage; remove if not actively used.**
  HTMX is actively used in two places — keep the script tag on all pages:
  1. `_forecast_row.html` — `hx-patch` on qty/reason inputs replaces the row `outerHTML` on `change`.
  2. `_header.html` — `hx-get="/dashboard/metrics"` refreshes the metrics zone when the period selector changes.
  3. `_dashboard_metrics.html` — `htmx-indicator` shows a loading state during the metrics fetch.

  Follow-up fixed on 2026-05-10: `forecast-table.js` now binds row events through an idempotent
  `bindForecastRow()` path and rebinds swapped rows via `htmx:afterSwap`, so `hx-swap="outerHTML"`
  keeps input recalculation, row detail, and restore interactions working after replacement.

---

## Backend Improvement Plan

Issues identified from architecture review on 2026-05-11. Work top-to-bottom within each phase.

### Phase 1 — Correctness & Reliability `priority: high`

- [x] **`product_monitor` 路由繞過 cache。**
  `product_monitor()` 直接呼叫 `build_forecast_page_context()` 而不走 `_build_cached_context()`，
  使跳單監控頁每次都重跑完整計算，沒有享受到任何 cache 效益。
  Fix: 讓 `product_monitor` 改呼叫 `_load_context_from_request()`（或 `_build_cached_context()`），
  與 dashboard / forecast 路由保持一致。

- [x] **`_find_or_create_close_snapshot` 靜默吞掉例外。**
  `except Exception: snapshot_rows = []` 把任何錯誤都轉成空快照存入 DB，
  無 log 也無回饋，可能留下靜默的資料錯誤。
  Fix: 至少 log 錯誤，或讓例外往上拋讓路由回傳 500。

### Phase 2 — Performance `priority: medium`

- [ ] **`_make_cache_key` 每次請求打 DB 兩次。**
  即使 cache hit，每個請求仍執行兩條 `SELECT`（`sales_records` count/max、
  `current_month_records` max）才能算出 key。
  Fix: 改用穩定 key + etag 比對，或在 write path 主動讓 key 失效，
  讓 hot-path 不需要先查 DB 才能決定要不要查 DB。

- [ ] **`cache.clear()` 太粗暴。**
  每次任何寫入（品項、調整、匯入）都清掉所有月份的快取，但不同月份的
  key 彼此獨立。Fix: 寫一個 `_invalidate_context_cache(year, month)` 只清
  當月的 key；跨月的品項設定異動才全清。

- [ ] **`_init_db` 每次啟動都跑 migration 探測。**
  每次 app 啟動都對每個欄位執行 `PRAGMA table_info()` 再決定是否 `ALTER TABLE`。
  Fix: 加入 `schema_version` 表，記錄已套用的版本號，啟動時只比對版本跳過已完成的 migration。

### Phase 3 — Maintainability `priority: low`

- [ ] **`build_forecast_page_context` 是 god function。**
  單一函式包含：載入資料、建立預測、套用調整、計算 dashboard、計算 monitor rows、
  計算 projections、取得 items，共 60+ 行呼叫 10+ 個函式，幾乎無法對單一步驟寫單元測試。
  Fix: 拆成 `_build_summary()`、`_build_monitor()`、`_build_health()` 等獨立步驟，
  `build_forecast_page_context` 變成純組裝。

- [ ] **`export` 路由保留無文件的 legacy 欄位名稱相容邏輯。**
  `legacy_manual_adjustments` 的 merge 路徑沒有說明是誰在用，造成兩條平行的
  form 解析路徑。Fix: 確認前端不再送舊格式後移除 legacy merge 邏輯。

- [ ] **`save_items` 路由直接內嵌 SQL 邏輯。**
  與「routes 薄、邏輯在 service」的設計方向不一致，若之後要加測試會是瓶頸。
  Fix: 抽出 `update_item_configs(db, items)` service function，路由只解 form 和呼叫它。

- [ ] **`upload_current_month` 有 inline import。**
  `from src.backend.etl import import_current_month` 在函式體內才 import，
  與其他路由的 top-level import 不一致。Fix: 移至檔案頂部。

- [ ] **`monthly_review` 的 except 是冗餘的。**
  `except (ValueError, Exception)` 中 `Exception` 已涵蓋 `ValueError`，多寫反而誤導。
  Fix: 改為 `except Exception`。

- [ ] **`load_item_configs` 迴圈跑兩次 rows。**
  先建 dict，再對同一個 `rows` 第二次迴圈補 normalized code alias，可以合在一個 pass。
  Fix: 在第一個迴圈內同時處理 normalized key。

---

## Working Rules

- Do one task at a time.
- Read `AGENTS.md`, this roadmap, and only the necessary active docs.
- Keep Flask routes thin.
- Keep calculation rules in testable backend services.
- Update docs when workflows, forecast rules, Excel shape, or UI structure change.
- Run the focused tests first, then the full suite when backend/routes/templates change.

## Recommended Verification

```powershell
D:\AI\python.exe -m pytest -q --basetemp=.test-dbs\pytest-tmp
D:\AI\python.exe -m py_compile app.py src\backend\app.py src\backend\sales_forecast.py src\backend\forecast_config.py src\backend\forecast_models.py src\backend\data_loader.py src\backend\forecast_engine.py src\backend\exporter.py src\backend\web\form_parser.py src\backend\web\forecast_presenter.py src\backend\operational_views.py
```
