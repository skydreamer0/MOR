# MOR Roadmap

Last reviewed: 2026-06-02

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

#### AH-1: ETL 年份寫死（高優先，靜默失效）

- 症狀：`BUDGET_FILE_PATTERN = "2026預算報表*.xlsx"` 和 `default_year=2026` 寫死在 `etl.py`，2027 年起靜默失效，需手動改源碼。
- 修正：從 `ForecastConfig` 讀取 `current_year`，或從 Excel 檔名自動推斷年份；`default_year` 改為參數化。
- 涉及檔案：`src/backend/etl.py`、`src/backend/forecast_config.py`。

#### AH-2: `/close-month` 與 `/snapshots/save` 繞過 ContextCache

- 症狀：`close_product_monitor_month` 和 `save_snapshot_route` 直接呼叫 `build_forecast_page_context()`，不走 `_build_cached_context()`，每次執行都重建整個上下文，與其他路由行為不一致。
- 修正：改為呼叫 `_build_cached_context(year, month)`。
- 涉及檔案：`src/backend/app.py`（兩個路由函式）。

#### AH-3: `build_forecast_page_context` 的 `data_base_path` 是死參數

- 症狀：`operational_views.build_forecast_page_context()` 接受 `data_base_path: Path`，但立刻轉給 `forecast_workbench_context.build()`，後者完全不使用它；`app.py` 多處傳入此參數都是無效呼叫。
- 修正：移除 `operational_views.build_forecast_page_context()` 的 `data_base_path` 參數，同步更新 `app.py` 的五個呼叫點。
- 涉及檔案：`src/backend/operational_views.py`、`src/backend/app.py`。

#### AH-4: `src/backend/app.py` 模組層級副作用

- 症狀：第 606 行 `app = create_app()` 在模組層級執行，import 此模組即觸發 DB 初始化與 Flask 應用建立；根目錄 `app.py` import `create_app` 時已隱含觸發一次建立。
- 修正：刪除 `src/backend/app.py` 的模組層級 `app = create_app()`；統一由根目錄 `app.py` 或 `if __name__ == "__main__"` 啟動。
- 涉及檔案：`src/backend/app.py`。

#### AH-5: `forecast_engine.py` 死代碼函式

- 症狀：`_month_quantity()` 和 `_month_amount()`（第 163–178 行）從未被呼叫；實際使用的是函式內部定義的 `_pqty`/`_pamt` closure。
- 修正：直接刪除兩個函式。
- 涉及檔案：`src/backend/forecast_engine.py`。

#### AH-6: `ForecastOptions.excluded_item_ids` 應為 `frozenset`

- 症狀：`@dataclass(frozen=True)` 中的 `set[str]` 欄位不可雜湊，違反 `frozen` 的語意預期（frozen dataclass 理應可做 dict key / set member）。
- 修正：型別改為 `frozenset[str]`，更新 `forecast_workbench_context.py` 傳入端。
- 涉及檔案：`src/backend/forecast_models.py`、`src/backend/forecast_workbench_context.py`。

#### AH-7: `excluded_items.json` 舊版遷移碼

- 症狀：`sync_excel_to_db()` 仍讀取並遷移 `excluded_items.json`（舊格式）；現有部署早已完成遷移，此段碼只增加混淆。
- 修正：確認無現存 `excluded_items.json` 後，移除對應的讀取與 INSERT 邏輯。
- 涉及檔案：`src/backend/etl.py`。

#### AH-8: ContextCache 不支援多 Worker（文件限制）

- 症狀：`_global_version` / `_month_versions` 存在 Python 物件、`SimpleCache` 為 in-process；若部署多 Worker（gunicorn multi-process），invalidation 不跨進程傳播，不同 Worker 會返回不同版本資料。
- 修正（文件層面）：在 `context_cache.py` 加上說明「必須單 Worker 部署」；未來若需多 Worker 再評估改用 Redis/Memcached 後端。
- 涉及檔案：`src/backend/context_cache.py`。

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
