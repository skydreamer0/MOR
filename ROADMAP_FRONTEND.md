# 前端改善 Roadmap（FE-7 ~ FE-17）

Last reviewed: 2026-08-02

延續 `ROADMAP.md` 已完成的 FE-1 ~ FE-6。本檔為前端剩餘工作的 source of truth；
主 `ROADMAP.md` 只保留一行指標，細節寫在這裡。

遵循主 ROADMAP 的規則：不做大範圍重構，一次收一個接縫，先寫測試再改行為。

## 進度

| 項目 | 狀態 |
|---|---|
| FE-7 htmx 本地化 | ✅ 完成（2026-08-01） |
| FE-8 Forecast 四階門檻 | ✅ 完成（2026-08-01） |
| FE-9 統一 class 詞彙 | ✅ 完成（2026-08-01，ADR-0004） |
| FE-10 fmt.js 唯一格式化來源 | ✅ 完成（2026-08-01） |
| FE-15 sparkline design token | ✅ 完成（2026-08-01） |
| FE-11 forecast-table.js 模組封裝 | ✅ 完成（2026-08-01） |
| FE-12 Jinja base layout | ✅ 完成（2026-08-01） |
| FE-13 依頁面載入 JS | ✅ 完成（2026-08-01） |
| FE-14 Canvas HiDPI 抽共用 | ✅ 完成（2026-08-02，4 處全收，helper 移入 `static/js/canvas.js`） |
| FE-16 CSS 死碼與重複配色 | ✅ 完成（2026-08-02） |
| FE-17 `items.html` 孤兒樣板 | ✅ 完成（2026-08-02） |

FE-7 驗收已補齊（2026-08-01，實際起 app 走查）：

- `window.htmx.version === "1.9.10"`，來源 `/static/js/vendor/htmx.min.js`。
- 整個 session 41 個網路請求**全部指向 localhost，零外部請求**——沒有可失敗的外部相依，
  等價於離線可用（比模擬斷網更直接的證據）。
- Dashboard 切月：`GET /dashboard/metrics?month=6&year=2026 → 200`，metrics 區塊正確 swap。
- Forecast 存檔：`PATCH /forecast/row/佑成藥局__N9AB0 → 200`，列 outerHTML swap，
  重新載入頁面後值仍在（完整往返）。測試後已還原原值。
- Console 零錯誤。

---

## 現況體檢摘要

下表是 2026-08-01 動工前的體檢數字，保留作為對照；括號內是 FE-7~FE-17 完成後的現況。

| 面向 | 動工前 → 現況 |
|---|---|
| 頁面樣板 | 8 個各自複製 doctype/head/body 骨架 → 骨架收斂到 `_base.html`；`items.html` 已刪（FE-17），customers/products 併為 `_analytics_page.html` |
| CSS | 3796 行、`:root` 60 個 token、350 個 class（27 個無引用） → 約 3630 行，死 class 已清 |
| JS | 10 支、約 2260 行，無 build step（ADR-0001） → 11 支（新增 `canvas.js`），全部 IIFE 封裝 |
| htmx | 外部 CDN → vendor 進 `static/js/vendor/`，全站零外部請求 |

---

## P0 — 會實際壞掉

### FE-7 htmx 本地化（移除 CDN 依賴）

**問題**：`templates/_head_assets.html:2` 從 `unpkg.com` 載入 htmx 1.9.10。
MOR 是本機離線 workbench，且有 release 打包流程（`build/`、`dist/`、GitHub Actions）。
離線環境下 htmx 靜默失效，直接失能的功能：

- `templates/_forecast_row.html:35,52` — 預估欄位 `hx-patch` 自動存檔
- `templates/_header.html:43,45` — Dashboard 期間切換 `hx-get` 局部更新

**做法**：把 htmx 1.9.10 min 檔 vendor 進 `static/js/vendor/htmx.min.js`，
`_head_assets.html` 改用 `url_for('static', ...)`，移除 `integrity`/`crossorigin`。
確認 release 打包腳本會帶上 `static/js/vendor/`。

**驗收**：斷網啟動 app，Forecast 改數字能存檔、Dashboard 切月份會更新。
`tests/test_release_packaging.py` 覆蓋 vendor 檔案存在。

---

### FE-8 Forecast 達成率補上四階門檻

**問題**：FE-5 宣稱四階門檻已統一，但 `static/js/forecast-table.js:133` `updateRateElement`
仍是舊的二階邏輯（`<80 → .low`、`>=100 → .high`），90–99 與 80–89 兩階在
Forecast 頁看不出來，跟 Dashboard／客戶／商品分析頁顯示不一致。

CSS 端對應 `static/css/mor.css:1247-1258` 的 `.rate.low` / `.rate.high` /
`.rate:not(.low):not(.high)` 三態，需一併收斂。

**做法**：`updateRateElement` 改呼叫 `AnalyticsFmt.budgetRate()`，套用統一 class 詞彙（見 FE-9）。

**驗收**：`tests/js/forecast-table.test.js` 已存在，於其中補上四個門檻邊界（100 / 99 / 89 / 79）的案例。

---

## P1 — 語意層真正收斂

### FE-9 統一達成率 class 詞彙

**問題**：同一組四階語意目前有三套互不相通的 class 名稱。

| 來源 | 詞彙 |
|---|---|
| `static/js/analytics-renderer.js:424` `_rateCls` | `positive / warning / caution / negative` |
| `templates/_value_macros.html:16` `achievement()` | `success-text / rate-warning / caution-text / danger-text` |
| `static/js/forecast-table.js:133` | `low / high`（二階，見 FE-8） |

**做法**：選定一組為正典（建議 `positive/warning/caution/negative`，與 JS 端一致且語意中性），
另一組在 CSS 收成 alias 或直接改掉樣板。決策寫進 `docs/adr/`。

**Stop rule**：若牽動超過三個檔案的大量改動，先停下回報。

---

### FE-10 `fmt.js` 收斂為唯一格式化來源

**問題**：`AnalyticsFmt` 目前只有 `static/js/analytics-table.js:33` 一個消費者。
另外兩支各自重寫一份：

- `static/js/forecast-table.js:1-6` — 自有 `formatter` / `_fp` / `_pct` / `_sign`
- `static/js/analytics-renderer.js:420-433` — 自有 `_signStr` / `_rateCls` / `_diffCls`

門檻常數 100/90/80 因此有三份硬編碼副本，而 `fmt.js` 早已 export
`BUDGET_RATE_ACHIEVED` / `_WARNING` / `_CAUTION`。

**做法**：兩支改為委派 `AnalyticsFmt`，硬編碼常數全部改引用 export。

**驗收**：`node --test tests/js/fmt.test.js`；grep 確認 `100`/`90`/`80` 門檻不再散落。

---

### FE-11 `forecast-table.js` 模組封裝

**問題**：820 行、約 40 個 function 與模組狀態（`_viewMode`、`_customerFilter`、
`_detailRowId`）全部裸露在 global scope。其餘三支（`fmt.js`、`analytics-table.js`、
`analytics-renderer.js`）都是 IIFE。命名衝突風險高，且無法被 node:test 匯入測試。

**做法**：包成 IIFE + `module.exports` guard，沿用 `fmt.js` 的既有寫法。
只匯出 HTML 內聯呼叫實際需要的名稱。

**驗收**：Forecast 頁全功能手動走查（編輯、篩選、抽屜、快照、匯出）+ FE-8 的測試。

---

## P2 — 結構整理

### FE-12 Jinja base layout

**問題**：8 個頁面樣板各自複製 `<!doctype html>` / `<head>` / `<body>` 骨架。
`templates/customers.html` 與 `templates/products.html` 更是雙胞胎——
diff 只有 12 處，全是「客戶↔商品」字串與 `idPrefix`。

**做法**：
1. 建 `templates/_base.html`，各頁改 `{% extends %}`。
2. `customers.html` / `products.html` 併為共用 analytics 樣板，差異用參數帶入。

---

### FE-13 依頁面載入 JS

**問題**：`_head_assets.html` 對所有頁面同步載入 `fmt.js` + `analytics-renderer.js` +
`analytics-table.js`（約 34KB），但實際用量：

| 頁面 | 是否用到 |
|---|---|
| index / customers / products | ✅ |
| settings / items / monthly_review / product_monitor | ❌ 完全沒用 |

（forecast 頁不直接引用，但 `forecast-table.js` 依賴 `AnalyticsRenderer`。）
且這三支沒有 `defer`，而 `behaviors.js` / `ui-feedback.js` 有——載入策略不一致。

**做法**：`_head_assets.html` 只留全站共用的；analytics 三支改由需要的頁面自行載入，
並統一加上 `defer`。

---

### FE-14 Canvas HiDPI 樣板抽共用

**問題**：`devicePixelRatio` → 設 `width`/`height` → `ctx.scale` 這段重複四次：
`analytics-renderer.js:98`、`analytics-renderer.js:454`、
`gap-sparkline.js:19`、`forecast-table.js:16`。

**做法**：抽一個 `setupCanvas(canvas, fallbackW, fallbackH)` 放進 `analytics-renderer.js` 並匯出。

---

### FE-15 `gap-sparkline.js` 改用 design token

**問題**：`static/js/gap-sparkline.js:3-10` 硬編 `#22c55e` / `#ef4444` / `#94a3b8` /
`#f97316`，完全繞過 CSS 的 977 個變數。`analytics-renderer.js` 至少在檔頭註解標明了
對應的 token，這支連註解都沒有。

**做法**：最低限度補上與 `mor.css` token 的對應註解（比照 `analytics-renderer.js:11-15`）；
若不影響繪製效能，改為開場一次性讀取 CSS 變數並快取。

---

## P3 — 清理

### FE-16 CSS 死碼與重複配色

**死 class（350 中的 27 個，`htmx-request` 為 htmx 內建，保留）**：
`site-header`、`site-nav`、`split-layout`、`dashboard-grid`、`dashboard-heading`、
`detail-block`、`detail-block-title`、`detail-budget`、`detail-kv-grid`、
`detail-kv-grid--3col`、`detail-kv-head`、`detail-kv-label`、`health-list`、
`metric-wide`、`monitor-note`、`review-metric-card-sm`、`review-secondary-metrics`、
`bottom-bar-actions`、`close-status-panel`、`close-status-panel--closed`、
`close-status-time`、`dist-count--slight`、`dist-dot-slight`、`status-slight`、
`status-no_history`、`tool-counts`。

刪除前逐一確認不是後端動態組出來的（`status-{{ row.status_key }}` 這類）。

**重複配色**：同一組四階 → token 的映射在 `mor.css` 的
920、1077、1136、1208、1229、1741 行各展開一次，差別只在 scope 前綴。
FE-9 定案後一併收斂。

---

## 全部完成

FE-7 ~ FE-17 均已完成。新工作請往下加，並同步更新上面的進度表。

**FE-14 收尾記錄**：`setupCanvas` 最終落在獨立的 `static/js/canvas.js`（不是
`analytics-renderer.js`），因為 Product Monitor 在 FE-13 之後不載入 analytics bundle。
四個重複點全部收斂。`gap-sparkline.js` 原本讀 `offsetWidth`／`offsetHeight`，
已統一為 `clientWidth`／`clientHeight`——瀏覽器實測佈局後的 canvas 兩者相等（347×80），
不是只從 CSS 推論。載入順序由 `tests/test_app.py::test_canvas_helper_loads_before_every_consumer` 保護。

**FE-17 連帶清理**：刪掉 `items.html` 後 `.management-panel`、`.management-panel p`、
`.item-code` 三條 CSS 一併變成死碼，已移除；`.management-table` 仍由 `settings.html` 使用，保留。

## 驗證指令

```powershell
node --test tests/js/fmt.test.js tests/js/analytics-table.test.js tests/js/monitor-table.test.js
D:\AI\python.exe -m pytest tests\test_frontend_js.py tests\test_ui_smoke.py tests\test_app.py -q --basetemp=.pytest-tmp
```
