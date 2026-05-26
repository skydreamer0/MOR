# MOR Roadmap

## MOR Architecture Refactor Roadmap

### Current Architecture Status

The architecture refactor is being executed one seam at a time. The current backend keeps Flask routes as request/response adapters while moving forecast workflow complexity into deeper modules.

Completed seams:

1. Forecast workbench context module.
2. Forecast write workflow refactor.
3. Export summary preparation.
4. Snapshot row serialization.
5. Item/settings write workflow form parsing.
6. Dashboard analytics template context.
7. Product monitor template context.
8. Forecast row identity helper foundation.

Current module boundaries:

- `src/backend/forecast_workbench_context.py` builds the workbench-ready forecast context.
- `src/backend/forecast_write_workflow.py` owns forecast row override persistence.
- `src/backend/forecast_export_workflow.py` owns export summary preparation.
- `src/backend/snapshot_service.py` owns snapshot persistence and forecast-row snapshot serialization.
- `src/backend/item_settings_workflow.py` owns item/settings request-form parsing and item config payload normalization.
- `src/backend/dashboard_analytics_workflow.py` owns dashboard analytics/template context assembly.
- `src/backend/product_monitor_workflow.py` owns product monitor template context assembly.
- `src/backend/row_identity.py` owns the legacy forecast row identity make/parse helper surface.
- `src/backend/operational_views.py` still owns view models and operational presentation helpers.
- `src/backend/app.py` still owns Flask request parsing, response rendering, redirects, cache invalidation, and remaining route-local workflow glue.

### Refactor Principles

- Small seams only.
- Characterization tests before refactor.
- Preserve external behaviour.
- Routes handle request/response only.
- Deep modules own workflow complexity.
- No broad rewrite.
- No unrelated feature work.

### Completed Work

#### `forecast_workbench_context.py`

- What moved inward: target resolution, DB input loading, forecast enrichment, projection pass, dashboard metrics, monitor rows, data health, and settings items.
- Public interface: `build(forecast_config, db, target_source, *, today=None)`.
- Tests protecting it: `test_forecast_workbench_context_build_matches_legacy_context_contract`, plus `tests/test_operational_views.py` and `tests/test_app.py`.
- Validation used: `D:\AI\python.exe -m pytest tests\test_operational_views.py -q`, `D:\AI\python.exe -m pytest tests\test_app.py -q`, and `py_compile` for touched backend modules.

#### `forecast_write_workflow.py`

- What moved inward: forecast row override quantity coercion and `forecast_adjustments` persistence.
- Public interface: `save_row_override(db, row_id, manual_qty, reason, year, month, *, updated_by="User")`.
- Tests protecting it: `test_forecast_write_workflow_save_row_override_persists_adjustment`, adjustment save route tests, and stale export signature tests.
- Validation used: `D:\AI\python.exe -m pytest tests\test_operational_views.py -q`, `D:\AI\python.exe -m pytest tests\test_app.py -q`, and `py_compile` for touched backend modules.

#### `forecast_export_workflow.py`

- What moved inward: submitted manual adjustment application, adjustment reason overlay, row amount recalculation, and export summary total rebuild.
- Public interface: `prepare_export_summary(summary, manual_adjustments, adjustment_reasons)`.
- Tests protecting it: `test_prepare_export_summary_applies_adjustments_reasons_and_totals`, export route tests, and `tests/test_exporter.py`.
- Validation used: `D:\AI\python.exe -m pytest tests\test_exporter.py -q`, `D:\AI\python.exe -m pytest tests\test_operational_views.py -q`, `D:\AI\python.exe -m pytest tests\test_app.py -q`, and `py_compile` for touched backend modules.

#### `snapshot_service.py`

- What moved inward: forecast row to snapshot row serialization for close-month and manual snapshot saves.
- Public interface: `serialize_forecast_rows_for_snapshot(rows)`.
- Tests protecting it: `test_serialize_forecast_rows_for_snapshot_preserves_snapshot_row_contract`, snapshot service persistence tests, and snapshot/close-month route tests.
- Validation used: `D:\AI\python.exe -m pytest tests\test_snapshot_service.py -q --basetemp=.pytest-tmp`, `D:\AI\python.exe -m pytest tests\test_app.py -q -k "snapshot or close_month" --basetemp=.pytest-tmp`, and `py_compile` for touched backend modules.

#### `item_settings_workflow.py`

- What moved inward: `POST /items/save` request-form parsing for `product_codes`, per-product checkbox flags, `price_quantity_*`, and `item_status_*`.
- Extraction boundary: `src/backend/item_settings_workflow.py` returns normalized payload dictionaries; `src/backend/app.py` still calls `update_item_configs(db, items)`, invalidates cache, and returns settings HTML.
- Public interface: `build_item_config_payloads_from_form(form)`.
- Tests protecting it: `test_build_item_config_payloads_from_form_preserves_item_settings_payload_shape`, plus item/settings route characterization tests in `tests/test_app.py`.
- Validation used: `D:\AI\python.exe -m pytest tests\test_item_settings_workflow.py -q --basetemp=.pytest-tmp`, `D:\AI\python.exe -m pytest tests\test_app.py -q -k "item_settings or items_route or exclusions_page_redirects or item_management_exclusion" --basetemp=.pytest-tmp`, and `py_compile` for touched backend modules.

#### `dashboard_analytics_workflow.py`

- What moved inward: dashboard template context assembly for remaining days, monitor status distribution, customer risk ranking, high-risk monitor rows, data issue labels, and analytics slices.
- Extraction boundary: `src/backend/dashboard_analytics_workflow.py` builds the existing template-key dictionary; `src/backend/app.py` still owns route error handling, fallback empty context, and template rendering.
- Public interface: `build_dashboard_template_context(context, *, today=None)`.
- Tests protecting it: `test_build_dashboard_template_context_preserves_dashboard_analytics_contract`, plus dashboard/homepage route tests in `tests/test_app.py`.
- Validation used: `D:\AI\python.exe -m pytest tests\test_dashboard_analytics_workflow.py -q --basetemp=.pytest-tmp`, `D:\AI\python.exe -m pytest tests\test_app.py -q -k "dashboard or homepage" --basetemp=.pytest-tmp`, and `py_compile` for touched backend modules.

#### `product_monitor_workflow.py`

- What moved inward: product monitor template context assembly for period, rows, import messages, latest import batch, and close-month record.
- Extraction boundary: `src/backend/product_monitor_workflow.py` builds the existing template-key dictionary; `src/backend/app.py` still owns request loading, error capture, upload/import routes, close-month routes, cache invalidation, redirects, and template rendering.
- Public interface: `build_product_monitor_template_context(context, db, *, fallback_year, fallback_month, error_message=None, import_message=None, import_error=None)`.
- Tests protecting it: `test_build_product_monitor_template_context_uses_context_period_and_rows`, `test_build_product_monitor_template_context_preserves_fallback_when_context_missing`, plus product monitor route/import/close-month tests in `tests/test_app.py`.
- Validation used: `D:\AI\python.exe -m pytest tests\test_product_monitor_workflow.py -q --basetemp=.pytest-tmp`, focused `tests\test_app.py` product monitor tests, and `py_compile` for touched backend modules.

#### `row_identity.py`

- What moved inward: legacy `customer__product_code` row identity creation/parsing helper surface.
- Extraction boundary: `src/backend/row_identity.py` preserves the current readable row ID contract; `src/backend/monthly_review.py` uses the helper on a read-only merge path. Write/export/form paths still use the existing legacy IDs and should be migrated only after delimiter/collision characterization tests exist.
- Public interface: `make_row_id(customer_name, product_code)` and `parse_row_id(row_id)`.
- Tests protecting it: `test_make_and_parse_row_id_preserves_legacy_customer_product_contract`, `test_parse_row_id_preserves_legacy_missing_product_fallback`, plus `tests/test_monthly_review.py`.
- Validation used: `D:\AI\python.exe -m pytest tests\test_row_identity.py tests\test_monthly_review.py -q --basetemp=.pytest-tmp`, plus route/export/snapshot focused tests and full suite.

### Remaining Refactor Plan

#### 1. Forecast row identity migration

Purpose: migrate remaining row identity builders/parsers to `row_identity.py` in small TDD slices before moving deeper product monitor row calculation or monthly review seams.

Boundary: keep the readable legacy `customer__product_code` contract until route, export, snapshot, and monthly review characterization tests prove any delimiter/collision migration path.

Next smallest implementation seam:

- Add delimiter/collision characterization tests, then migrate one remaining builder path such as `forecast_engine._row_id` or `daily_sales_importer.fetch_daily_actuals_by_row_id`.

### Execution Order

1. Forecast row identity.
2. Product monitor row calculation.
3. Workbench context internals.
4. Close-month workflow.

### Per-Seam Execution Template

For every seam:

1. Architecture phase.
2. Parallel subagent inspection.
3. Characterization tests.
4. Small extraction.
5. Route simplification.
6. Targeted validation.
7. Update `ROADMAP.md`.

### Validation Matrix

```powershell
D:\AI\python.exe -m pytest tests\test_operational_views.py -q
D:\AI\python.exe -m pytest tests\test_app.py -q
D:\AI\python.exe -m pytest tests\test_exporter.py -q
D:\AI\python.exe -m pytest tests\test_snapshot_service.py -q
D:\AI\python.exe -m py_compile src\backend\forecast_workbench_context.py src\backend\forecast_write_workflow.py src\backend\forecast_export_workflow.py src\backend\snapshot_service.py src\backend\operational_views.py src\backend\app.py
```

### Stop Rules

Stop and report before implementation if:

- A seam touches analytics and write workflows at the same time.
- More than three files need major changes.
- Tests do not clearly describe current behaviour.
- Route behaviour may change.
- Existing dirty files may be overwritten.

---

## Product Vision

MOR 是一個緊湊的多頁業務操作工具，供業務團隊在月底執行預測、審查跳單、匯出報表。

核心四頁：
1. **Dashboard** — 快速業績總覽（YTD、GAP、預算達成）
2. **Product Monitor** — 每日跳單風險審查
3. **Forecast** — 月度預測調整與 Excel 匯出
4. **Settings** — 品項規則與資料健康檢查

---

## What's Next

### 技術債（唯一剩餘）

- [x] **`build_forecast_page_context` god function 重構**
  `operational_views.py` 中單一函式包含資料載入、預測建立、調整套用、dashboard 計算、monitor rows、projections、items 共 60+ 行，呼叫 10+ 個 service。無法對單一步驟寫單元測試。
  **Fix**: 拆成 `_build_summary()`、`_build_monitor()`、`_build_health()` 等獨立步驟，`build_forecast_page_context` 變成純組裝函式。
  **注意**: 這是較大規模重構，需先在 branch 上完成再合入。

### 功能 Backlog（依優先度排序）

1. **Product view page** — 以品項為維度的業績彙總，架構與 Customer View 相同

### 已完成功能

- [x] **Browser 端多頁 UI 驗收** — 19 個 smoke tests 覆蓋四頁操作流程與邊界情況
- [x] **Budget coverage warning 串入 UI** — settings 頁以 `alert-info` 顯示未對應預算品項
- [x] **Customer view page** (`/customers`) — 以客戶為維度，含 YTD 彙總、月別展開、趨勢 sparkline

---

## Working Rules

- 一次只做一個任務。
- 讀 `AGENTS.md`、本 roadmap、以及當下任務所需的最少文件。
- Flask routes 保持薄；計算規則放在可測試的 backend service。
- 工作流程、預測規則、Excel 格式、UI 結構有異動時同步更新文件。
- 改動 backend / routes / templates 時：先跑聚焦測試，再跑完整 suite。

### Verification

```bash
python3 -m pytest -q
python3 -m py_compile src/backend/app.py src/backend/etl.py src/backend/operational_views.py src/backend/forecast_engine.py src/backend/exporter.py src/backend/analytics.py src/backend/history_service.py
```

---

## Completed Work

### Frontend — 2026-05-09 to 2026-05-10

**Phase 1 — Correctness**
- [x] 統一 row visibility 為單一機制（`row.hidden` 單一 pass，消除三套 filter 互相覆蓋）
- [x] 欄位群組分隔線改用 `col-group-start` class，移除 `nth-child` 位置依賴

**Phase 2 — Design System**
- [x] DESIGN.md token 值與 `mor.css` 同步
- [x] 唯一 hardcode 顏色 `#eef6ff` 移入 `--row-hover` design token

**Phase 3 — Maintainability**
- [x] Customer dropdown 統一進 `recalculate()` 單一 visibility pass
- [x] `<thead>` 抽出為 `_forecast_thead.html` shared partial
- [x] HTMX 使用審查（確認 `hx-patch`、`hx-get` 均有效使用，`htmx:afterSwap` 重綁 row events）

### Backend Round 1 — 2026-05-11

**Phase 1 — Correctness & Reliability**
- [x] `product_monitor` 路由改走 `_load_context_from_request()`，享受 cache
- [x] `_find_or_create_close_snapshot` 例外改為 log + re-raise

**Phase 2 — Performance**
- [x] Cache key 改用版本計數器（`_month_versions`），hot-path 不再打 DB
- [x] `cache.clear()` 改為 `_invalidate_context_cache(year, month)` 精準清除
- [x] `_init_db` 改用 `schema_migrations` 版本表，啟動時跳過已套用的 migration

**Phase 3 — Maintainability**
- [x] `export` 路由移除 legacy `manual_adjustments` 相容層
- [x] `save_items` 路由抽出 `update_item_configs(db, items)` service function
- [x] `upload_current_month` inline import 移至檔案頂部
- [x] `monthly_review` 冗餘的 `except (ValueError, Exception)` 改為 `except Exception`
- [x] `load_item_configs` 迴圈合為單一 pass

### Backend Round 2 — 2026-05-15

**Phase 4 — Reliability & Data Integrity**
- [x] `sync_excel_to_db` 全部 DB 寫入改為單一 transaction，任一步驟失敗全部 rollback
- [x] `etl.py` 5 處 `print()` 改為 `logging.getLogger(__name__)`
- [x] Budget DELETE 年份從 hardcode `2026` 改為從資料動態提取

**Phase 5 — Testing Coverage**（測試數：184 → 201）
- [x] 新增 `tests/test_exporter.py`（4 tests）
- [x] 新增 `tests/test_analytics.py`（5 tests）
- [x] 新增 `tests/test_history_service.py`（8 tests）

**Phase 6 — Validation & Configuration**
- [x] 4 個寫入路由加入 `1 <= month <= 12` 與 `2000 <= year <= 2100` 範圍驗證
- [x] `data_validator.py` 新增 `validate_budget_coverage()` 函式
- [x] `requirements.txt` 所有依賴鎖定版本（Flask==2.3.2、pandas==2.2.3 等）
