# MOR Roadmap

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
