# MOR 前端介面顯示邏輯統一與優化計畫

## 1. 現狀問題分析 (Identified Issues)

在檢視 `templates/index.html` 與 `static/js/forecast-table.js` 的程式碼後，發現前端「顯示邏輯」存在以下不一致的情況：

1. **Jinja2 (後端渲染) 與 JavaScript (前端動態計算) 邏輯重複且分歧**：
   - 頁面初次載入時，Jinja 會計算「上月達成率」、「上月 GAP」、「達成率」、「差異」，並加上對應的 HTML class。
   - 當使用者手動調整數量時，`forecast-table.js` 的 `renderRow` 函式會重新計算「達成率」與「差異」，並嘗試更新 DOM，但其邏輯與 Jinja 渲染的略有不同（例如 `rate` 的計算與 class 切換）。

2. **數值與色彩格式 (Visual Formatting) 不一致**：
   - **上月 GAP (Last Month GAP)**：使用 `+` / `-` 符號與整數格式 (`{:+.0f}`)，並帶有 `.gap-value.positive` / `.gap-value.negative` 的顏色標示 (綠/紅)。
   - **差異 (Diff)**：代表「最終預估」與「實際數量 (本月)」的差值，卻僅顯示標準的兩位小數格式 (`{:,.2f}`)，沒有正負號與顏色標示。

3. **名詞定義與精確度 (Precision)**：
   - 數量比較有時用整數（上月 GAP），有時用兩位小數（差異），容易造成視覺上的混亂。作為銷售數量的比較，通常應統一為整數 (`.0f` / `maximumFractionDigits: 0`)。

4. **表頭 (Table Header) 與表格容器的樣式不一致**：
   - **`index.html`**：使用 `.table-wrap` 容器來產生內部滾動條，配合 `th { position: sticky; }` 與 `border-collapse: separate`，並利用 `::after` 畫出表頭底線與陰影。
   - **`items.html`**：使用 `.item-grid` 與 `border-collapse: collapse`，且直接將 table 放在帶有 padding 的 `.management-panel` 內。這導致表頭的 sticky 行為失效或視覺突兀，且 `padding` 與邊線畫法也與首頁不同。

---

## 2. 改善與優化方案 (Proposed Solutions)

為了讓程式碼更好維護，且使用者體驗達到企業級標準，建議採取以下重構策略：

### 方案 A：統一 UI 狀態管理 (單一真實來源)
既然試算表具有「連動計算」的特性，**所有會變動的數值與顏色邏輯，應全權交由 JavaScript 統一處理**。
- **Jinja 職責縮減**：Jinja 僅負責將原始數值 (Raw data) 放入 HTML `data-*` 屬性中，不負責計算與上色。
- **JS 統一渲染**：在 `forecast-table.js` 中新增 `formatRate()` 與 `formatGap()` 輔助函式。在頁面載入完成時 (`DOMContentLoaded`)，立刻執行一次全表的 `recalculate()`，讓 JS 統一負責所有欄位（包含靜態的上月 GAP/達成率）的格式化與上色。這能徹底消滅 Jinja 與 JS 邏輯不一致的問題。

### 方案 B：視覺語彙標準化 (Standardize Visual Indicators)
針對數據呈現制定嚴格的 Design Tokens 規則：
1. **百分比 (Rate)**：
   - `< 80%`：套用 `.rate.low` (紅色背景/字體)。
   - `>= 100%`：套用 `.rate.high` (綠色背景/字體)。
   - `80% ~ 99%`：套用中性警告色（現有 CSS 已支援）。
2. **差異值 (Gap / Diff)**：
   - 全面套用 `.gap-value` 樣式。
   - `> 0`：顯示 `+` 符號，套用 `.positive` (綠色 text)。
   - `< 0`：顯示 `-` 符號，套用 `.negative` (紅色 text)。
   - 將「差異」明確更名為「同期差異」或「落差」，並統一顯示為 **整數**，捨去不必要的小數位數，保持介面清爽。

### 方案 C：表格與表頭元件共用化 (Table Component Standardization)
1. **統一容器與滾動行為**：所有資料表格（包含品項管理）都應包裝在 `.table-wrap` 中，確保表頭 sticky 固定效果一致，且不被外部 panel 的 padding 影響。
2. **統一 CSS Tokens**：
   - 廢除 `.item-grid` 特殊的 `border-collapse` 與 `padding` 覆寫。
   - 讓所有 `th` 統一享有相同的字體大小、高度、以及 `::after` 下底線陰影效果，確保各個頁面的表格看起來出自同一套 Design System。

---

## 3. 實作步驟 (Implementation Steps)

1. **更新 `templates/index.html`**：
   - 移除 `<td>` 內繁瑣的 Jinja `{% if %}` 判斷式。
   - 將所有需要前端計算與呈現的欄位，給予明確的 `data-*-display` 屬性（如 `data-lm-gap-display`, `data-diff-display`），內容留空或保留基本的預設值防閃爍。
2. **更新 `static/js/forecast-table.js`**：
   - 撰寫 `formatGap(value)` 與 `formatRate(value)` 輔助函式。
   - 在 `renderRow` 內，統一處理「上月達成率」、「上月 GAP」、「達成率」、「差異」的 DOM 內容與 class 替換。
   - 將數值 formatter 統一：數量 GAP 使用 `formatter` (0位小數)，預估數量可保留 `precisionFormatter` (2位小數) 若業務有需求。
3. **檢查 CSS (`static/css/mor.css`)**：
   - 確保 `.gap-value`, `.positive`, `.negative`, `.rate`, `.low`, `.high` 等類別樣式正確對齊，無衝突。

---

## 結論
此優化能大幅減少 HTML 模板的肥大，將「商業計算邏輯」與「視覺呈現」完美分離，且能保證無論是剛載入頁面，或是使用者手動輸入調整後，呈現的邏輯絕對 100% 一致，符合企業級應用的嚴謹度。
