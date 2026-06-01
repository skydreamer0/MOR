# MOR Roadmap

Last reviewed: 2026-06-01

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
- `src/backend/forecast_workbench_inputs.py` owns DB input loading and budget target records for the forecast workbench context.
- `src/backend/amount_calculation.py` owns forecast row amount inclusion and quantity-to-amount calculation.
- `src/backend/forecast_write_workflow.py` owns forecast row override persistence.
- `src/backend/forecast_export_workflow.py` owns export summary preparation.
- `src/backend/snapshot_service.py` owns snapshot persistence, forecast-row snapshot serialization, and final/close-month snapshot immutability.
- `src/backend/item_settings_workflow.py` owns item/settings request-form parsing and item config payload normalization.
- `src/backend/dashboard_analytics_workflow.py` owns dashboard analytics/template context assembly.
- `src/backend/product_monitor_workflow.py` owns product monitor template context assembly.
- `src/backend/product_monitor_rows.py` owns product monitor row view models, row calculation, status labels, and monthly history lookup.
- `src/backend/row_identity.py` owns canonical forecast row identity make/parse helpers.
- `src/backend/operational_views.py` still owns shared operational view models, analytics helpers, remaining budget/history presentation helpers, and compatibility facades.
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

#### BF-5: Close-Month 非原子操作（孤兒快照風險）

- 症狀：`_find_or_create_close_snapshot` 先建快照再呼叫 `close_month`；若後者失敗，留下孤兒快照，下次結帳撿到錯誤快照。
- 修正：屬於既有 Seam 3（Close-Month Workflow）的一部分，在該 seam 中以 transaction 包裹整個操作。
- 暫不獨立修正，等 Seam 3 展開時一起處理。

#### BF-6: Monthly Review 廣義例外吞掉邏輯錯誤

- 症狀：`except Exception as exc:` 捕捉所有例外（含程式邏輯錯誤），只顯示 `str(exc)`，難以 debug。
- 修正：縮窄為具體例外型別（`ValueError`, `LookupError`），其餘讓 Flask error handler 處理。
- 涉及檔案：`src/backend/app.py`（`monthly_review` route）。

Boundary for BF batch:
- 每個 BF item 獨立 commit，不合併進其他 seam。
- 不改動 route 對外行為（回傳內容、重導向目標、狀態碼）。
- BF-0 完成後跑 `pytest -q` 確認 218→271 通過。
- BF-2 完成後確認 `with db.get_connection() as conn:` 呼叫方不需修改。

---

### 1. Workbench Context Internals

Goal: keep `forecast_workbench_context.py` as the public context builder while moving remaining summary enrichment, health, projection, and monitor assembly details into smaller testable helpers.

Boundary:

- Keep `build(forecast_config, db, target_source, *, today=None)` stable unless a test-protected API change is necessary.
- Do not touch export/write workflows in the same seam.

### 2. Amount Calculation Seam

Goal: expand the new amount calculation seam so monthly review and raw forecast engine behavior cannot diverge silently from dashboard/export calculations.

Boundary:

- Characterize current behavior before changing formulas.
- Treat `exporter.py` primarily as workbook output, not the owner of pricing rules.

### 3. Close-Month Workflow

Goal: move remaining close-month route-local orchestration into a backend workflow/service.

Boundary:

- Snapshot immutability is already owned by `snapshot_service.py`.
- This seam should own route orchestration, validation, close-record creation, cache invalidation points, and redirect/message behavior.

### 4. Context Cache Seam

Goal: extract cache key/invalidation state from `app.py` into a small `ContextCache` seam if cache behavior starts blocking route simplification.

Priority: low. Current helper functions are acceptable until other route seams are quieter.

## Product Backlog

1. Product view page: product-level sales summary, similar in shape to the completed Customer View.

Hold feature work until the active refactor batch is small and verified, unless the user explicitly prioritizes the feature.

## Completed Feature Work

- Browser multi-page UI smoke coverage.
- Budget coverage warning in Settings UI.
- Customer view page (`/customers`) with YTD summary, month expansion, and sparkline.
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
D:\AI\python.exe -m pytest tests\test_operational_views.py -q --basetemp=.pytest-tmp
D:\AI\python.exe -m pytest tests\test_app.py -q --basetemp=.pytest-tmp
D:\AI\python.exe -m pytest tests\test_exporter.py tests\test_snapshot_service.py -q --basetemp=.pytest-tmp
```

Quick syntax validation:

```powershell
D:\AI\python.exe -m py_compile app.py src\backend\app.py src\backend\sales_forecast.py src\backend\forecast_config.py src\backend\forecast_models.py src\backend\data_loader.py src\backend\forecast_engine.py src\backend\projection_engine.py src\backend\operational_views.py src\backend\etl.py src\backend\exporter.py src\backend\web\form_parser.py src\backend\web\forecast_presenter.py
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
