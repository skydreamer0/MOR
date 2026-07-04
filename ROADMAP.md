# MOR Roadmap

Last reviewed: 2026-07-03

This file is the active source of truth for MOR planning. Historical implementation plans and architecture review artifacts should not be used as implementation context unless this roadmap explicitly points to them.

## Current Direction

MOR is a local Flask/Jinja/SQLite sales forecast workbench. Keep the product compact, operational, table-first, and predictable.

Architecture direction:

- Keep Flask routes thin: request parsing, response rendering, redirects, and cache invalidation only.
- Move workflow complexity into small backend modules one seam at a time.
- Preserve current external behavior while refactoring.
- Write characterization tests before changing calculation, lookup, export, or row identity behavior.
- Avoid broad rewrites and do not re-inline workflow modules into routes.

## Current Module Boundaries

- `src/backend/forecast_workbench_context.py` builds the workbench-ready forecast context, owns `ForecastPageContext`, and owns summary-local latest-order-date enrichment.
- `src/backend/forecast_page_context.py` owns Forecast page render-data assembly, risk levels, visible/discontinued row split, visible totals, and forecast review signatures.
- `src/backend/forecast_workbench_inputs.py` owns DB input loading, budget target records, and the row-facing input interface for the forecast workbench context.
- `src/backend/amount_calculation.py` owns forecast row amount inclusion and quantity-to-amount calculation.
- `src/backend/dashboard_metrics.py` owns dashboard KPI metrics.
- `src/backend/data_health_summary.py` owns data health summary view model and builder.
- `src/backend/forecast_write_workflow.py` owns forecast row override persistence.
- `src/backend/forecast_export_workflow.py` owns export summary preparation.
- `src/backend/monthly_review_context.py` owns Monthly Review page/export context assembly.
- `src/backend/snapshot_service.py` owns snapshot persistence, forecast-row snapshot serialization, and final/close-month snapshot immutability.
- `src/backend/item_settings_workflow.py` owns item/settings request-form parsing and item config payload normalization.
- `src/backend/item_settings_repository.py` owns item setting persistence.
- `src/backend/settings_context.py` owns Settings page data-health, budget-coverage, target, and error fallback context assembly.
- `src/backend/dashboard_analytics_workflow.py` owns dashboard template context assembly.
- `src/backend/analytics.py` owns reusable analytics slices plus dashboard status distribution and customer risk ranking helpers.
- `src/backend/product_monitor_workflow.py` owns product monitor template context assembly.
- `src/backend/product_monitor_month_context.py` owns Product Monitor month-level projection, dashboard, and monitor-row orchestration.
- `src/backend/product_monitor_rows.py` owns product monitor row view models, row calculation, status labels, and monthly history lookup.
- `src/backend/row_identity.py` owns canonical forecast row identity make/parse helpers.
- `src/backend/monthly_review_data.py` owns Monthly Review DB read rules for closed/open month fallback, budgets, actuals, forecasts, product names, price quantities, and historical unit-price fallback.
- `src/backend/app.py` still owns Flask request/response wiring, redirects, cache invalidation, and remaining route-local workflow glue.

## Completed Architecture Seams

1. Forecast workbench context module.
2. Forecast write workflow refactor.
3. Export summary preparation.
4. Snapshot row serialization.
5. Item/settings write workflow form parsing.
6. Dashboard analytics template context.
7. Product monitor template context.
8. Forecast row identity helper foundation.
9. Forecast row identity lookup migration across operational, history, and projection paths.
10. Product monitor row calculation module extraction.
11. Forecast workbench input-loading and latest-order-date enrichment extraction.
12. Forecast workbench page-context type ownership extraction.
13. Close-month snapshot immutability and Forecast UI delete guard.
14. Forecast workbench input loader ownership cleanup.
15. Amount calculation seam foundation.
16. Dashboard analytics helper relocation.
17. Forecast page presentation context extraction.
18. Monthly Review context package foundation.
19. Settings data-health context extraction.
20. `operational_views.py` retirement.
21. Monthly Review data read seam.
22. Forecast workbench row-facing input interface.
23. Product Monitor month context extraction.

## Release Packaging Roadmap

Goal:

- Ship MOR as clean Windows and macOS GitHub Releases without bundling local Excel files, SQLite databases, logs, or cache.
- Keep the app directly runnable from the release bundle while storing mutable runtime data in a user-writable location outside the packaged files.

Planned slices:

1. Remove tracked local data files from the release surface and keep the ignore rules explicit.
2. Define a release/runtime path contract for app data, the SQLite workbench, and any optional imported files.
3. Add a GitHub Actions release workflow that builds Windows and macOS artifacts separately.
4. Update release and local-setup docs so the first-run and import/sync flows are obvious.

Parallelization note:

- Once the runtime path contract is defined, the packaging workflow, path/bootstrap work, and docs/update work can be split across subagents because they do not need to edit the same files at the same time.

## Frontend UI/UX Improvement Roadmap

Goal:

- Improve operation safety (confirm dialogs, header action separation), input efficiency (month switcher, keyboard navigation, sorting), and polish (fonts, focus, empty states) without changing forecast logic, Excel schema, or backend behavior.

Plan:

- Active plan: `docs/design/2026-07-04-frontend-uiux-improvement-roadmap.md` (6 work packages, WP1–WP6, priority P0–P2, designed so each WP can be executed by a different agent).

Parallelization note:

- WP1 and WP2 both touch `templates/_header.html` and `static/css/mor.css` and must run sequentially; WP3 (`forecast-table.js`) and WP4 (`monitor-table.js`) can run in parallel with them; WP5/WP6 go last to reduce rebase cost.

## Cloud Agent Architecture Roadmaps

Use this section as the current staged roadmap for cloud/remote agents. Work one phase at a time, keep behavior stable, and update this section after each completed phase.

Plain-language summary:

- MOR is not broken. It has reached a stage where many features have already moved into smaller modules, but a few old middle stations still make the code harder to follow.
- First, retire `operational_views.py` as the old front desk. It still redirects callers to work now owned elsewhere, which makes humans and agents think it is more important than it is.
- Second, clean the Forecast page route. The `/forecast` route still decides display ordering, discontinued rows, risk levels, visible totals, and similar presentation rules. Those should move behind a backend page-context module.
- Third, package Monthly Review. The calculation modules are already fairly clean, but the route still has to remember the full serving order: summary, actions, customers, products, bias, trend, and chart.
- Fourth, clean Settings later. The Settings route mixes data health, budget coverage, direct DB lookup, and fallback shape. It is less urgent, but it will keep getting noisier if left inside the route.

Overall goal:

- Retire `src/backend/operational_views.py` as a broad compatibility module.
- Keep Flask routes thin.
- Move page/template assembly into small backend modules.
- Preserve the Flask/Jinja/vanilla JS architecture from ADR 0001.
- Avoid database, UI, and calculation rewrites unless the phase explicitly says so.

### Phase 0: Baseline and Safety - Completed 2026-06-03

Goal: establish a clean test baseline before moving imports or modules.

Completed result:

- Baseline operational/workbench tests passed before Phase 1 edits.
- `operational_views.py` export/caller classification was completed by parallel read-only inspection.
- No production code was moved in this phase.

Tasks:

1. Run the focused operational/view tests and record current failures, if any.
2. Inspect only current callers of `operational_views.py`, `forecast_workbench_context.py`, `amount_calculation.py`, and `app.py`.
3. Classify every `operational_views.py` export as one of:
   - real owned behavior
   - compatibility facade
   - test-only legacy import
4. Do not move code in this phase unless needed to fix a failing baseline test.

Likely files:

- `src/backend/operational_views.py`
- `src/backend/forecast_workbench_context.py`
- `src/backend/amount_calculation.py`
- `src/backend/app.py`
- `tests/test_operational_views.py`
- `tests/test_forecast_workbench_context.py`

Verification:

```powershell
D:\AI\python.exe -m pytest tests\test_operational_views.py tests\test_forecast_workbench_context.py -q --basetemp=.pytest-tmp
```

### Phase 1: Amount Calculation Import Cleanup - Completed 2026-06-03

Goal: make amount calculation callers use `amount_calculation.py` directly instead of routing through `operational_views.py`.

Completed result:

- `app.py`, `forecast_export_workflow.py`, and `forecast_workbench_context.py` now import amount helpers directly from `amount_calculation.py`.
- Unused amount facade exports were removed from `operational_views.py`.
- `tests/test_architecture_imports.py` now guards this seam so amount helpers do not drift back through `operational_views.py`.

Tasks:

1. Change production imports of these helpers to direct imports from `src/backend/amount_calculation.py`:
   - `forecast_amount_total`
   - `last_year_amount_total`
   - `recalculate_forecast_amounts`
   - `amount_for_quantity` where applicable
2. Update tests so amount calculation behavior is asserted against `amount_calculation.py`.
3. Leave temporary compatibility aliases in `operational_views.py` only if needed by older tests during the phase.
4. After tests pass, remove unused amount aliases from `operational_views.py`.

Likely files:

- `src/backend/amount_calculation.py`
- `src/backend/operational_views.py`
- `src/backend/forecast_export_workflow.py`
- `src/backend/forecast_workbench_context.py`
- `src/backend/app.py`
- `tests/test_operational_views.py`
- `tests/test_exporter.py`

Verification:

```powershell
D:\AI\python.exe -m pytest tests\test_operational_views.py tests\test_exporter.py tests\test_forecast_workbench_context.py -q --basetemp=.pytest-tmp
```

### Phase 2: Forecast Workbench Context Canonical Import - Completed 2026-06-03

Goal: make `forecast_workbench_context.py` the only normal entry point for building `ForecastPageContext`.

Completed result:

- `app.py` now imports `forecast_workbench_context.build` as the local `build_forecast_page_context` name.
- Route calls now use the canonical builder signature without the legacy `data_base_path` compatibility argument.
- Internal tests no longer import `ForecastPageContext` or `build_forecast_page_context` from `operational_views.py`.
- The `operational_views.py` compatibility shim is intentionally left for later deletion/minimization.

Tasks:

1. Replace production imports of `operational_views.build_forecast_page_context` with the canonical workbench context builder.
2. Remove or shrink the `data_base_path` compatibility argument path.
3. Update tests that still import `ForecastPageContext` or `build_forecast_page_context` from `operational_views.py`.
4. Keep a short compatibility shim only if a route migration would otherwise become too large.
5. Document the canonical import path in `ROADMAP.md` if the phase changes module ownership.

Likely files:

- `src/backend/forecast_workbench_context.py`
- `src/backend/operational_views.py`
- `src/backend/app.py`
- `tests/test_forecast_workbench_context.py`
- `tests/test_operational_views.py`
- `tests/test_app.py`

Verification:

```powershell
D:\AI\python.exe -m pytest tests\test_forecast_workbench_context.py tests\test_operational_views.py tests\test_app.py -q --basetemp=.pytest-tmp
```

### Phase 3: Dashboard and Analytics Helper Relocation - Completed 2026-06-03

Goal: move dashboard-facing analytics helpers out of `operational_views.py` into modules whose names match their purpose.

Completed result:

- `aggregate_to_analytics`, `build_status_distribution`, `build_customer_risk_ranking`, and `CustomerRiskItem` now live in `analytics.py`.
- `app.py` and `dashboard_analytics_workflow.py` import dashboard analytics helpers from `analytics.py`.
- `operational_views.py` no longer exports the dashboard analytics helper facades.
- Architecture tests guard the canonical import path.

Tasks:

1. Move or re-home:
   - `aggregate_to_analytics`
   - `build_status_distribution`
   - `build_customer_risk_ranking`
   - `CustomerRiskItem` if still needed
2. Prefer existing modules before adding new ones:
   - `dashboard_analytics_workflow.py` for dashboard template assembly
   - `analytics.py` for reusable analytics data shaping
3. Keep product monitor row calculation in `product_monitor_rows.py`.
4. Update imports and tests one helper group at a time.
5. Delete compatibility exports only after all callers move.

Likely files:

- `src/backend/dashboard_analytics_workflow.py`
- `src/backend/analytics.py`
- `src/backend/operational_views.py`
- `src/backend/app.py`
- `tests/test_dashboard_analytics_workflow.py`
- `tests/test_operational_views.py`

Verification:

```powershell
D:\AI\python.exe -m pytest tests\test_dashboard_analytics_workflow.py tests\test_operational_views.py tests\test_app.py -q --basetemp=.pytest-tmp
```

### Phase 4: Forecast Page Presentation Context - Completed 2026-06-03

Goal: move Forecast page render-data assembly out of the `/forecast` route.

Completed result:

- Added `forecast_page_context.py` for Forecast page render-data assembly.
- Moved row sorting, active/discontinued split, visible row limit, visible/unrendered totals, customer list, risk levels, and forecast review signature validation behind backend helpers.
- Kept `/forecast` responsible for loading context, finalized/snapshot lookup, and template rendering.
- Added characterization tests for presentation output and architecture guards for canonical imports.

Tasks:

1. Create a small backend module for Forecast page presentation context.
2. Move these route-local rules behind one interface:
   - row sorting
   - active/discontinued split
   - visible row limit
   - visible and unrendered totals
   - customer list
   - risk levels
   - forecast signature if it remains page-specific
3. Keep the route responsible only for target loading, context call, snapshot/finalized lookup, and `render_template`.
4. Add characterization tests before changing output shape.
5. Keep template variable names stable.

Likely files:

- `src/backend/app.py`
- `src/backend/forecast_page_context.py` or another clearly named new module
- `src/backend/amount_calculation.py`
- `templates/forecast.html`
- `tests/test_app.py`
- `tests/test_forecast_presenter.py`

Verification:

```powershell
D:\AI\python.exe -m pytest tests\test_app.py tests\test_forecast_presenter.py -q --basetemp=.pytest-tmp
```

### Phase 5: Monthly Review Context Package - Completed 2026-06-03

Goal: collapse repeated Monthly Review route orchestration into one backend context package.

Completed result:

- Added `monthly_review_context.py` to assemble summary, action lists, customer summary, product summary, forecast bias, trend, and optional trend chart.
- Updated Monthly Review HTML and export routes to use the same context builder.
- Kept `monthly_review.py` DB-only behavior unchanged.
- Replaced Monthly Review export broad exception handling with current route-level known error types.
- Added context tests and architecture guards for the shared route seam.

Tasks:

1. Create a monthly review context builder that returns:
   - summary
   - action lists
   - customer summary
   - product summary
   - forecast bias
   - trend
   - trend chart for HTML callers
2. Use the same context builder from the HTML route and export route where practical.
3. Keep `monthly_review.py` DB-only behavior unchanged.
4. Replace broad exception handling only with known current error types.
5. Add tests that verify HTML and export callers share the same assembled data.

Likely files:

- `src/backend/app.py`
- `src/backend/monthly_review.py`
- `src/backend/monthly_review_context.py` or another clearly named new module
- `src/backend/monthly_review_actions.py`
- `src/backend/monthly_review_chart.py`
- `src/backend/monthly_review_customers.py`
- `src/backend/monthly_review_export.py`
- `src/backend/monthly_review_forecast_bias.py`
- `src/backend/monthly_review_products.py`
- `src/backend/monthly_review_trend.py`
- `tests/test_monthly_review*.py`

Verification:

```powershell
D:\AI\python.exe -m pytest tests\test_monthly_review.py tests\test_monthly_review_actions.py tests\test_monthly_review_chart.py tests\test_monthly_review_customers.py tests\test_monthly_review_products.py tests\test_monthly_review_forecast_bias.py tests\test_monthly_review_trend.py -q --basetemp=.pytest-tmp
```

### Phase 6: Settings Data Health Context - Completed 2026-06-03

Goal: move Settings page data-health and budget-coverage assembly out of the route.

Completed result:

- Added `settings_context.py` to assemble Settings items, health, data issues, target year/month, and error fallback shape.
- Moved budget coverage SQL out of `app.py`.
- Kept Settings template variable names stable.
- Kept `item_settings_workflow.py` focused on form parsing and payload normalization.
- Added Settings context tests and architecture guards for the route seam.

Tasks:

1. Create a settings context builder that returns:
   - items
   - health
   - data issues
   - target year/month
   - error fallback shape
2. Move the budget coverage SQL out of `app.py`.
3. Keep settings template variable names stable.
4. Keep `item_settings_workflow.py` focused on form parsing and payload normalization.
5. Add tests for missing data, budget coverage warnings, and normal settings context.

Likely files:

- `src/backend/app.py`
- `src/backend/settings_context.py` or another clearly named new module
- `src/backend/data_validator.py`
- `src/backend/item_settings_workflow.py`
- `templates/settings.html`
- `tests/test_item_settings_workflow.py`
- `tests/test_data_validator.py`
- `tests/test_app.py`

Verification:

```powershell
D:\AI\python.exe -m pytest tests\test_item_settings_workflow.py tests\test_data_validator.py tests\test_app.py -q --basetemp=.pytest-tmp
```

### Phase 7: Final operational_views Deletion or Minimal Shim - Completed 2026-06-03

Goal: finish the retirement of `operational_views.py`.

Completed result:

- Re-ran import search for `operational_views`.
- Deleted `src/backend/operational_views.py`; no compatibility shim remains.
- Moved remaining production callers to canonical modules:
  - `dashboard_metrics.py`
  - `data_health_summary.py`
  - `forecast_workbench_context.py`
  - `forecast_workbench_inputs.py`
  - `item_settings_repository.py`
  - `product_monitor_rows.py`
- Moved remaining tests to canonical module imports and renamed `tests/test_operational_views.py` to `tests/test_forecast_workbench_helpers.py`.
- Updated `docs/architecture/current-architecture.md` and this roadmap.
- Added architecture guards that require the retired module to stay deleted and prevent runtime/unit-test imports from returning.

Tasks:

1. Re-run import search for `operational_views`.
2. If no production callers remain, either:
   - delete `operational_views.py`, or
   - keep a tiny deprecated shim only for deliberate compatibility.
3. Move remaining tests to canonical modules.
4. Update `docs/architecture/current-architecture.md` and this roadmap if module ownership changes.
5. Run full validation before claiming completion.

Likely files:

- `src/backend/operational_views.py`
- `src/backend/app.py`
- `docs/architecture/current-architecture.md`
- `ROADMAP.md`
- `tests/test_forecast_workbench_helpers.py`

Verification:

```powershell
D:\AI\python.exe -m pytest -q --basetemp=.pytest-tmp
```

### Phase Stop Rules

Stop and report before continuing if:

- A phase needs broad UI template changes.
- A phase changes forecast math, row identity, Excel schema, or DB schema.
- More than three production modules need major rewrites in one phase.
- Existing tests do not describe the current behavior clearly.
- `operational_views.py` deletion would require unrelated feature work.

## Active Refactor Queue

### 0. Architecture Bug Fix Batch (prerequisite for remaining seams)

架構審查發現的具體問題，按優先順序逐一修正。每個修正獨立 commit，可單獨驗證。

#### BF-0: Werkzeug 版本釘選（測試環境修復）

- 症狀：Flask 2.3.2 + Werkzeug 3.1.8 不相容，`test_app.py` 全數失敗。
- 修正：`requirements.txt` 加入 `werkzeug>=2.3.3,<3.0`，恢復 53 個路由測試。
- 涉及檔案：`requirements.txt`。

#### BF-1: PRG 修正（`/items/save` 表單重複送出）

- 症狀：`save_items()` POST 後直接 render 頁面，F5 重新整理觸發重複 POST。
- 修正：`return settings()` → `return redirect(url_for("settings"))`。
- 涉及檔案：`src/backend/app.py`。

#### BF-2: SQLite 連線未關閉（資源洩漏）

- 症狀：`sqlite3.Connection` 的 `with` block 只做 commit/rollback，不關閉連線；長時間執行累積未釋放連線。
- 修正：`MORDatabase.get_connection()` 改為 `@contextmanager`，在 `finally` 中明確 `conn.close()`。
- 涉及檔案：`src/backend/database.py`（呼叫方 `with db.get_connection() as conn:` 語法不變）。

#### BF-3: `_apply_reasons_and_budgets` 跨模組引用私有函式

- 症狀：`forecast_workbench_context.py` 引入底線前綴的私有函式，表示模組邊界洩漏。
- 修正：移除底線前綴，成為 `operational_views` 的公開 API。
- 涉及檔案：`src/backend/operational_views.py`、`src/backend/forecast_workbench_context.py`。

#### BF-4: SimpleCache 無界增長

- 症狀：`CACHE_DEFAULT_TIMEOUT=0`（永不過期）+ cache key 包含日期，每天產生新 key 且舊 key 永不清除，記憶體持續增長。
- 修正：`create_app` 的 cache config 加入 `CACHE_THRESHOLD: 500`（最多 500 條目，超過自動 LRU 淘汰）。
- 涉及檔案：`src/backend/app.py`。

#### BF-5: Close-Month 非原子操作（孤兒快照風險）✅ 完成（Seam 3）

- 症狀：`_find_or_create_close_snapshot` 先建快照再呼叫 `close_month`；若後者失敗，留下孤兒快照。
- 修正：建立 `close_month_workflow.execute_close_month()`，所有寫入共用單一 connection；`app.py` 移除兩步驟拆分邏輯。
- 涉及檔案：`src/backend/close_month_workflow.py`（新增）、`src/backend/app.py`。

#### BF-6: Monthly Review 廣義例外吞掉邏輯錯誤 ✅ 完成

- 症狀：`except Exception as exc:` 捕捉所有例外（含程式邏輯錯誤），只顯示 `str(exc)`，難以 debug。
- 修正：縮窄為具體例外型別（`ValueError`, `LookupError`），其餘讓 Flask error handler 處理。
- 涉及檔案：`src/backend/app.py`（`monthly_review` route）。

#### BF-7: `/sync` 回傳純文字（UX）✅ 完成

- 症狀：sync 後回傳純文字頁面，使用者需手動回上頁。
- 修正：改為 `redirect(url_for("dashboard", sync_message=...))` PRG 模式。
- 涉及檔案：`src/backend/app.py`。

Boundary for BF batch: ✅ 全數完成
- 每個 BF item 獨立 commit，可單獨驗證。
- 290 tests passing。

---

### 1. Workbench Context Internals ✅ 完成

Goal: keep `forecast_workbench_context.py` as the public context builder while moving remaining summary enrichment, health, projection, and monitor assembly details into smaller testable helpers.

完成內容：
- 移除 `app.py` dead import `build_monthly_review_report`（從未呼叫）
- `_patch_latest_order_dates`：測試改為從 `forecast_workbench_context` 引入（canonical 位置），移除 `operational_views` 的 proxy shim
- 新增 `_filter_visible_rows(summary, item_configs)` helper，從 `_build_summary` 提取 visibility filter 成具名函式，可獨立測試

### 2. Amount Calculation Seam ✅ 完成

Goal: expand the new amount calculation seam so monthly review and raw forecast engine behavior cannot diverge silently from dashboard/export calculations.

完成內容：
- 移除 `operational_views.py` 裡的四個 amount alias（`_dashboard_amount`、`_amount_from_latest_order_price`、`_latest_price_quantity`、`_is_amount_included`）
- 全部呼叫點改為直接使用 `amount_calculation.amount_for_quantity`
- `operational_views.py`：590 → 565 行（-25 行）
- 消除因 alias 分歧導致 amount 計算邏輯悄悄不一致的風險

### 3. Close-Month Workflow ✅ 完成（BF-5）

Goal: move remaining close-month route-local orchestration into a backend workflow/service.

完成內容：`close_month_workflow.py` 建立，包含原子寫入邏輯。`app.py` 路由已精簡為：建 context → 序列化 rows → 呼叫 `execute_close_month()`。

Boundary:

- Snapshot immutability is already owned by `snapshot_service.py`.
- Route only orchestrates: context build, row serialization, cache invalidation, redirect.

### 4. Context Cache Seam ✅ 完成

Goal: extract cache key/invalidation state from `app.py` into a small `ContextCache` seam if cache behavior starts blocking route simplification.

完成內容：
- 新增 `src/backend/context_cache.py`，`ContextCache` 類別封裝版本計數器與 key 生成
- `app.py` closure 中的 `_month_versions`、`_global_version` 及 5 個 helper 函式改以 `ctx_cache = ContextCache(flask_cache)` 取代
- `_invalidate_context_cache()` → `ctx_cache.invalidate()`，`_invalidate_all_context_cache()` → `ctx_cache.invalidate_all()`

### 5. Architecture Hygiene Batch

架構審查（2026-06-02）發現的具體問題，按優先順序修正。每個修正獨立 commit 可單獨驗證。

#### AH-1: ETL 年份寫死（高優先，靜默失效）✅ 完成

- 症狀：`BUDGET_FILE_PATTERN = "2026預算報表*.xlsx"` 和 `default_year=2026` 寫死在 `etl.py`，2027 年起靜默失效，需手動改源碼。
- 修正：預算檔搜尋改為跨年份 pattern，從預算 Excel 檔名推斷年份，並讓 `sync_excel_to_db()` 可用 `default_budget_year` 明確覆寫；`normalize_budget_targets()` 的 `default_year` 改為參數化且支援無「年」欄預算表。
- 涉及檔案：`src/backend/etl.py`、`tests/test_etl.py`。

#### AH-2: `/close-month` 與 `/snapshots/save` 繞過 ContextCache ✅ 完成

- 症狀：`close_product_monitor_month` 和 `save_snapshot_route` 直接呼叫 `build_forecast_page_context()`，不走 `_build_cached_context()`，每次執行都重建整個上下文，與其他路由行為不一致。
- 修正：改為呼叫 `_build_cached_context(year, month)`，並補路由 cache seam regression tests。
- 涉及檔案：`src/backend/app.py`（兩個路由函式）。

#### AH-3: `build_forecast_page_context` 的 `data_base_path` 是死參數 ✅ 完成

- 症狀：舊 `operational_views.build_forecast_page_context()` 曾接受 `data_base_path: Path`，但該參數不參與 context build；容易讓 route 呼叫看起來仍依賴 Excel base path。
- 修正：canonical `forecast_workbench_context.build()` 簽名只保留 `forecast_config`、`db`、`target_source` 與 keyword-only `today`；補 architecture guard 防止 `data_base_path` 參數回流。
- 涉及檔案：`src/backend/forecast_workbench_context.py`、`src/backend/app.py`、`tests/test_architecture_imports.py`。

#### AH-4: `src/backend/app.py` 模組層級副作用 ✅ 完成

- 症狀：`app = create_app()` 在 backend 模組層級執行，import `src.backend.app` 即觸發 DB 初始化與 Flask 應用建立；根目錄 `app.py` import `create_app` 時已隱含觸發一次建立。
- 修正：刪除 `src/backend/app.py` 的模組層級 `app = create_app()`；直接執行 backend 模組時改由 `if __name__ == "__main__"` 呼叫 `create_app().run(...)`，並補 architecture guard。
- 涉及檔案：`src/backend/app.py`、`tests/test_architecture_imports.py`。

#### AH-5: `forecast_engine.py` 死代碼函式 ✅ 完成

- 症狀：`_month_quantity()` 和 `_month_amount()` 從未被呼叫；實際使用的是函式內部定義的 `_pqty`/`_pamt` closure。
- 修正：刪除兩個函式，並補 architecture guard 防止 dead helpers 回流。
- 涉及檔案：`src/backend/forecast_engine.py`、`tests/test_architecture_imports.py`。

#### AH-6: `ForecastOptions.excluded_item_ids` 應為 `frozenset` ✅ 完成

- 症狀：`@dataclass(frozen=True)` 中的 `set[str]` 欄位不可雜湊，違反 `frozen` 的語意預期（frozen dataclass 理應可做 dict key / set member）。
- 修正：型別改為 `frozenset[str]`，預設值改為 `frozenset()`，並在 `__post_init__` 將既有 set/list 呼叫端正規化為 `frozenset`。
- 涉及檔案：`src/backend/forecast_models.py`、`tests/test_forecast.py`。

#### AH-7: `excluded_items.json` 舊版遷移碼 ✅ 完成

- 症狀：`sync_excel_to_db()` 仍讀取並遷移 `excluded_items.json`（舊格式）；現有部署早已完成遷移，此段碼只增加混淆。
- 修正：確認 repo 無現存 `excluded_items.json` 後，移除對應的讀取與 `item_configs` INSERT/UPDATE 遷移邏輯，並補 regression test 確認舊 JSON 不再影響 DB。
- 涉及檔案：`src/backend/etl.py`、`tests/test_etl.py`。

#### AH-8: ContextCache 不支援多 Worker（文件限制）

- 症狀：`_global_version` / `_month_versions` 存在 Python 物件、`SimpleCache` 為 in-process；若部署多 Worker（gunicorn multi-process），invalidation 不跨進程傳播，不同 Worker 會返回不同版本資料。
- 修正（文件層面）：在 `context_cache.py` 加上說明「必須單 Worker 部署」；未來若需多 Worker 再評估改用 Redis/Memcached 後端。
- 涉及檔案：`src/backend/context_cache.py`。

---

## Frontend Architecture Roadmap (2026-07-03)

前端接縫深化，來自 2026-07-03 架構審查（audit 報告候選 1–4）。與後端的
`codex/architecture-deepening` 分支（monthly_review_data reader、
ForecastRowMonthInput、product_monitor_month_context）**零檔案交集**，可獨立合併。
本節工作都在 `claude/epic-nightingale-9238a1` 分支上進行。

前端模組邊界（新增）：

- `static/js/fmt.js` owns semantic value formatting: 台灣慣例漲跌配色
  （rising/falling）與達成語意（positive/negative）的唯一 JS 定義點，門檻常數集中。
- `static/js/analytics-table.js` owns the analytics table controller:
  summary row rendering, sparkline scheduling, expandable detail rows,
  HTML escaping of entity labels, keyboard access. 介面：
  `AnalyticsTable.mount(tbody, slices, options)`。
- `templates/_value_macros.html` owns Jinja-side semantic formatting
  (yoy / achievement / accuracy / rank_change / signed_amount_gap)，
  是 `fmt.js` 的模板雙生，門檻必須與之同步。
- `static/js/analytics-renderer.js` 不變：owns canvas 繪圖與 metrics 計算。

### FE-1: 分析表控制器統一 ✅ 完成（commit 86ffec8）

- 症狀：customers.html、products.html、_dashboard_metrics.html 各有一份
  ~135 行幾乎相同的 inline 表格控制器；`entity_label` 未轉義直接進 innerHTML（XSS）；
  可展開列無鍵盤路徑。
- 完成內容：三份 inline script 收斂為 `analytics-table.js` 的 mount 呼叫
  （淨刪 385 行模板碼）；模組內統一 `escapeHtml`；可展開列加上
  tabindex / aria-expanded / Enter / Space。
- 測試：`tests/js/analytics-table.test.js`（node:test，經 `tests/test_frontend_js.py`
  pytest wrapper 執行，無 node 時 skip）。`buildRowCells` 為純函式，是測試面。

### FE-2: 漲跌/達成語意單一定義 ✅ 完成（commit 86ffec8）

- 症狀：「漲=紅、跌=綠；達成=綠、未達=紅」規則散落六處
  （Jinja macro、裸 Jinja 條件、三處 JS），門檻互相漂移。
- 完成內容：`_monthly_review_macros.html` 升格為全站 `_value_macros.html`
  （4 個 monthly review partial 的 import 已更新）；新增 `fmt.js` JS 雙生；
  product_monitor.html 與 _dashboard_metrics.html 中**完全等價**的
  inline 條件式改用 macro（YoY、達成率、signed gap 共 8 處）。
- 測試：`tests/js/fmt.test.js` 窮舉門檻邊界。

### FE-3: Forecast 列 data-state JSON 契約（待做，有前置條件）

- ⚠️ 前置條件：**等 `codex/architecture-deepening` 合併進 main 之後再做**。
  該分支正在改 `forecast_workbench_context.py` / `forecast_workbench_inputs.py`
  的預算語意（ForecastRowMonthInput），本項的上游正是這些模組。
- 症狀：Flask 與預估工作台之間的介面是 `_forecast_row.html` 上手寫的
  ~24 個 data-* 屬性，`forecast-table.js readRowState()` 逐一還原；
  衍生值（final forecast、diff、achievement rate）在
  `web/forecast_presenter._serialize_row`（Python，有測試）與
  `renderRow / refreshDetailBudget`（JS，無測試）各算一遍；
  htmx PATCH 換列與 JS recalculate() 是兩條更新路徑。
- 方案：每列狀態收斂成單一 `data-state='{{ row_state | tojson }}'`，
  內容直接由 `_serialize_row` 產生（schema 即該 dict，已被
  `tests/test_forecast_presenter.py` 覆蓋）；衍生數學只留 JS 一側；
  filter 用的 data-customer / data-search / data-status 保留為獨立屬性
  以維持 CSS selector。
- 涉及檔案：`templates/_forecast_row.html`、`static/js/forecast-table.js`、
  `src/backend/web/forecast_presenter.py`、`src/backend/app.py`
  （patch_forecast_row）。
- 先寫 characterization tests 鎖住 readRowState 對衍生值的現有輸出再動。

### FE-4: 版面行為去重（待做，快贏，無前置條件）

- 症狀：「main 高度 = 視窗 − sticky header」的 resize IIFE 複製在
  forecast.html、product_monitor.html、settings.html、customers.html、
  products.html 共 5 處；「捲動收合 summary/工具列」wheel+scroll 模式
  在 forecast.html 與 product_monitor.html 各一份。
- 方案：刪 5 個 IIFE，改純 CSS（`body { display:flex; flex-direction:column;
  height:100dvh }` + `main { flex:1; min-height:0 }`，header 已 sticky）；
  scroll-collapse 收成一個 `static/js/behaviors.js`，以
  `data-collapse-on-scroll` 屬性宣告。
- 涉及檔案：上列 5 個模板、`static/css/mor.css`（284–311 行的版面區塊）。
- 驗收：視覺不變、無 JS 高度覆寫；`test_ui_smoke.py` 全過。

### FE-5: 待使用者拍板的兩個語意分歧（決策項，非程式項）

重構時浮出、**刻意保留現狀**的行為分歧。統一任一者都是使用者可見的變更：

1. 達成率警戒門檻：`_value_macros.achievement` 與 monitor 主列用 **90**；
   product_monitor.html 月別對照表（近 6 月表格）與 `fmt.budgetRate` 用 **80**。
   同一個 85% 在不同表格呈現黃色或無色。
2. YoY 表示法：儀表板用 signed delta（`fmt.yoyDelta`，"+10.0%"）；
   客戶/商品分析頁用 ratio（`fmt.yoyRatio`，"110.0%"）。欄名都叫「YoY」。

拍板後改 `fmt.js` 常數 + `_value_macros.html` 對應 macro 即可（單點修改）。

### FE-6: Web Interface Guidelines 修正批次（backlog，2026-07-03 審查）

已修：三處 innerHTML XSS、分析頁可展開列鍵盤化（隨 FE-1）。未修，按優先序：

1. `mor.css` 全檔無 `@media (prefers-reduced-motion: reduce)`；
   `pulse-dot` 無限動畫、flash、save-pulse 不會停用。
2. forecast.html `#save-status` 缺 `aria-live="polite"`（儲存狀態 SR 聽不到）；
   index.html `#metrics-zone`（htmx swap 目標）同。
3. product_monitor.html 展開列：`aria-expanded` 在不可聚焦的 `<tr>` 上、
   只綁 click 無鍵盤路徑（比照 FE-1 的做法補 tabindex + keydown）。
4. forecast-table.js snapshot modal 無 Escape 關閉、無 focus trap；
   row-detail 抽屜同樣無 Escape。
5. `_header.html:22` 檔案上傳 input 用 `display:none`（鍵盤不可達），
   改 `.sr-only`（product_monitor.html 的 import 表單已是正確範例）。
6. items.html checkbox 未包 label（此頁疑似被 settings.html 取代，
   先確認是否直接刪除頁面）。
7. 全站缺 skip link；forecast 篩選狀態不反映在 URL；
   `.summary` 收合動畫 transition max-height（應改 transform/opacity）。

### Frontend Validation

```powershell
# JS 單元測試（node 22+，無 build step）
node --test tests/js/fmt.test.js tests/js/analytics-table.test.js

# 經 pytest（含模板 smoke）
D:\AI\python.exe -m pytest tests\test_frontend_js.py tests\test_ui_smoke.py tests\test_app.py -q --basetemp=.pytest-tmp
```

Frontend stop rules：改 `fmt.js` 或 `_value_macros.html` 的門檻常數屬於
行為變更，需 FE-5 拍板；模板改動後必跑 `test_ui_smoke.py` + `test_app.py`。

---

## Product Backlog

(empty — all planned items complete)

## Completed Feature Work

- Browser multi-page UI smoke coverage.
- Budget coverage warning in Settings UI.
- Customer view page (`/customers`) with YTD summary, month expansion, and sparkline.
- Product view page (`/products`) with YTD summary, month expansion, and sparkline.
- Forecast item status layering: discontinued products render in a collapsed section below active forecast rows.
- Path unification: `src/backend/` is the canonical backend implementation path; root `app.py` is only a launch wrapper.

## Closed Historical Plans

The following planning artifacts have been absorbed, completed, or superseded and were moved to archive:

- Forecast item status layering plan — completed and absorbed into feature history.
- MOR stability and hygiene plan — absorbed into this roadmap; remaining work is tracked above.
- Old refactor plan — superseded; its workflow-inlining recommendation conflicts with the current route-thinning direction.
- Path unification plan — completed; canonical path is now documented here and in active architecture docs.
- Roadmap before/after HTML report — review artifact absorbed into this roadmap.
- Old project architecture and implementation plan — superseded by `docs/architecture/current-architecture.md` plus this roadmap.
- Duplicate infrastructure API spec — stale duplicate of API notes; keep `docs/design/api-spec.md` active.
- UI design system Phase 0 inventory — historical UI inventory; keep `DESIGN.md` and `docs/design/ui-design-system-roadmap.md` active for UI work.

If a future task needs historical context, ask the user before reading archived plans.

## Per-Seam Execution Template

For every refactor seam:

1. Inspect only related active files.
2. Write or update characterization tests.
3. Make the smallest extraction or migration.
4. Keep route behavior stable.
5. Run focused validation.
6. Update this roadmap if the next seam changes.

Use subagents only for broad audits, independent investigations, or explicit user requests.

## Validation Matrix

Focused backend route/service validation:

```powershell
D:\AI\python.exe -m pytest tests\test_forecast_workbench_helpers.py -q --basetemp=.pytest-tmp
D:\AI\python.exe -m pytest tests\test_app.py -q --basetemp=.pytest-tmp
D:\AI\python.exe -m pytest tests\test_exporter.py tests\test_snapshot_service.py -q --basetemp=.pytest-tmp
```

Quick syntax validation:

```powershell
D:\AI\python.exe -m py_compile app.py src\backend\app.py src\backend\sales_forecast.py src\backend\forecast_config.py src\backend\forecast_models.py src\backend\data_loader.py src\backend\forecast_engine.py src\backend\projection_engine.py src\backend\forecast_workbench_context.py src\backend\forecast_page_context.py src\backend\dashboard_metrics.py src\backend\data_health_summary.py src\backend\monthly_review_context.py src\backend\settings_context.py src\backend\etl.py src\backend\exporter.py src\backend\web\form_parser.py src\backend\web\forecast_presenter.py
```

Full validation before broad backend completion claims:

```powershell
D:\AI\python.exe -m pytest -q
```

## Stop Rules

Stop and report before implementation if:

- A seam touches analytics and write workflows at the same time.
- More than three files need major changes.
- Tests do not clearly describe current behavior.
- Route behavior may change.
- Existing dirty files may be overwritten.
- A historical plan conflicts with this roadmap.
