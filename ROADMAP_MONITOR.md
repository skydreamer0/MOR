# 跳單監控改善 Roadmap

## 目標
將 `/monitor/products` 從靜態快照升級為「出貨節律分析儀」，讓業務一眼判斷客戶出貨週期是否在惡化。

---

## ✅ 已完成

### UI 基礎改善（本次 branch）
- **整列點擊展開**：移除小按鈕，整列 `cursor:pointer`，chevron CSS 旋轉，符合 Linear/GitHub 業界慣例
- **週期狀態正常加 badge**：`正常` 改為綠色 badge，與逾期/接近對齊，欄位視覺一致
- **展開詳情卡重設計**：頂部摘要列 + 三欄主體（數量比較 / 金額比較 / 週期推估）+ 備註 footer

### Phase 1 — 後端間隔序列（本次 branch）
**檔案**：`src/backend/projection_engine.py`、`src/backend/operational_views.py`

- `_workday_gaps()` — 從歷史出貨日計算工作天間隔序列（最近 8 筆）
- `ProjectionResult.gap_history: list[int]` — 隨 projection 帶出間隔序列
- `ProductMonitorRow.gap_history / gap_trend / gap_trend_delta` — 三個新欄位
- `_compute_gap_trend()` — 比較最近 3 筆 vs 整體平均，±10% 門檻判定趨勢

### Phase 2 — 主表趨勢欄（本次 branch）
**檔案**：`templates/product_monitor.html`、`static/css/mor.css`

- 新增「間隔趨勢」欄（第 12 欄）
- ↗ 紅色 = 間隔拉長（警示）、↘ 綠色 = 縮短（健康）、→ 穩定
- `data-gap-history / data-gap-avg / data-gap-current` 帶入 `<tr>` 供 JS 使用

### Phase 3 — Gap Sparkline（本次 branch）
**檔案**：`static/js/gap-sparkline.js`（新檔）、`templates/product_monitor.html`、`static/css/mor.css`

- Canvas 柱狀走勢圖：X = 各次出貨，Y = 工作天間隔
- 顏色規則：低於平均 → 綠、超過平均 → 紅、近平均 → 灰
- 橫虛線 = 歷史平均基準
- 最右橘色虛線柱 = 目前已過工作天數（進行中）
- 展開時 redraw（canvas hidden → visible 需重算寬度）

---

## 🔲 待實作

### Phase 4 — 近 6 月對照表 + 預算進度條

**目標**：詳情卡補充歷史量的脈絡，讓業務不只看現在，也看趨勢。

**後端**（`src/backend/operational_views.py` / `app.py`）
- 查 `month_close_records` JOIN `daily_sales_actuals` 取最近 6 個已結月
- 每月帶：`actual_qty / budget_qty / last_year_qty`
- 加到 `ProductMonitorRow.monthly_history: list[dict]`（或獨立 dataclass）

**前端**（`templates/product_monitor.html`）
```
月份    實際量   預算量   去年同期
04月    1,200   1,500    1,100   → 80%預算 / +9% YoY
03月    1,450   1,500    1,300
…
```

**預算進度條**（當月）
```
預算 ████████████ 1,500
目前 ████████░░░░ 1,000  (67%)
推估 ███████████░ 1,380  (92%)
```
- 三段同軸比較，視覺化達成狀況

---

### Phase 5 — 主表欄位精簡（可選）

目前主表 12 欄有點多，評估是否合併：
- 「距出貨」+ 「週期狀態」→ 合併為一欄顯示 `17天 / 逾期`
- 「去年成長率」+ 「預算達成率」→ 考慮用 mini 雙格顯示

---

### Phase 6 — 匯出 / 篩選加強（低優先）

- 匯出目前篩選結果為 CSV
- 狀態篩選加入「週期逾期」單獨選項
- 搜尋支援多關鍵字（空格分隔）

---

## 技術備注

| 資料來源 | 說明 |
|---|---|
| `sales_records.order_date` | 歷史出貨日（2年），Gap Sparkline 的基礎 |
| `daily_sales_actuals.sales_date` | 當月出貨日，補最新一筆 |
| `workday_calendar` | 工作天計算依據 |
| `month_close_records` | Phase 4 近 6 月對照的結月記錄 |

Gap trend 門檻：recent_avg vs overall_avg ±10%（`_compute_gap_trend`）
Gap history 上限：最近 8 筆（`_workday_gaps`，`[-8:]`）
