# MOR UI Refactor Roadmap (專項改善計畫)

本計畫旨在將 MOR 的介面從基礎原型提升至 **「現代化數據工作台 (Modern Data Workbench)」** 等級，對齊 Tier-1 企業內部工具標準。

## 核心目標
1. **提升專業感**：引入更精緻的色彩、字體與間距系統。
2. **強化操作效率**：優化高密度表格的掃描性與數據對比度。
3. **即時狀態感知**：確保手動調整與系統預估的區隔清晰直覺。

---

## 階段 1：基礎設計系統與 Token (Foundation) ✅ DONE
**目標：建立可維護的 CSS 變數系統。**

- [x] **顏色系統 (Color Palette)**：
    - 引入更深邃的 `Slate Gray` 作為中性背景。
    - 精確定義 `Teal-600` 作為品牌主色，並提供 Hover、Active、Subtle、Ring 狀態。
    - 優化 `Success`, `Warning`, `Danger` 的背景、文字與邊框對比。
- [x] **字體系統 (Typography)**：
    - 預設使用 `Inter` (數字) 與 `Microsoft JhengHei` (中文) 的組合。
    - 建立微縮字級規範 (11px ~ 28px)，適配高密度作業。
- [x] **空間系統 (Spacing)**：
    - 統一使用 4px 為基數的 Padding/Margin 規範 (`--sp-1` ~ `--sp-10`)。
- [x] **陰影與圓角系統**：
    - 五級陰影 (`--shadow-xs` ~ `--shadow-lg` + `--shadow-up`)。
    - 四級圓角 (`--radius-sm` ~ `--radius-xl`)。
- [x] **動畫系統**：
    - 統一的過渡時間 (`--duration`) 與緩動函數 (`--ease-out`)。

## 階段 2：佈局元件重構 (Layout Components) ✅ DONE
**目標：釋放垂直空間，優化工作流。**

- [x] **精簡導覽列 (Sticky Header)**：
    - 縮小標題高度 (h1: 16px)，改為「MOR + 子頁面標題」格式。
    - 導航連結移除分隔符，改用間距 + hover 效果。
    - 增強毛玻璃效果 (`blur(12px) saturate(1.8)`)。
- [x] **指標卡片區 (Metric Summary)**：
    - 從邊框卡片改為「無邊框/淺背景」設計 (`--surface-subtle`)。
    - 移除 `box-shadow`，改用 hover 背景變深暗示互動性。
    - 標題字級縮小至 `--text-xs` + `uppercase`。
- [x] **吸附式動作條 (Fixed Bottom Bar)**：
    - 增強毛玻璃效果 (`blur(16px)`)。
    - 使用 `--shadow-up` 提供清晰的深度層次。
    - 總額數字使用 `--text-2xl` (28px) 配合 `letter-spacing: -0.02em`。
- [x] **統一頁面導航**：
    - 三個模板 (`index.html`, `items.html`, `exclusions.html`) 統一使用相同的 header 結構。
    - 移除 `items.html` 的行內 CSS，整合至共用設計系統。
- [x] **輸入框初步優化**：
    - 表內輸入框 (`.qty`, `.reason`) 改為「透明邊框 + subtle 背景」風格。
    - Hover 時顯示邊框，Focus 時使用 `--accent-ring`。

## 階段 3：核心數據表格優化 (Data Grid Deep-dive) ✅ DONE
**目標：達成 spreadsheet-native 的極致體驗。**

- [x] **表頭與對齊 (Header & Alignment)**：
    - Sticky Header 改用 `::after` 偽元素投射陰影，取代 `box-shadow`。
    - 表頭字級縮至 `--text-xs` (11px)，搭配 `letter-spacing: 0.04em`。
    - 確保金額與數量嚴格右對齊（使用 Tabular Numbers）。
- [x] **Zebra Striping**：
    - 奇偶列交替淺色背景 (`rgba(248, 250, 252, 0.5)`)，提升掃描效率。
    - Hover 統一使用 `#eef6ff` 藍色調。
- [x] **狀態標記與 Badge**：
    - 重設計為 Pill 圓角 (`border-radius: 10px`) + 圓點指示器 (`::before`)。
    - 「未到週期」改為灰色中性風格，降低視覺干擾。
- [x] **互動列狀態 (Row States)**：
    - `Excluded (已排除)`：使用 `line-through` 刪除線 + 灰色文字（取代 opacity）。
    - `Edited (已手動調整)`：淺藍背景 + 左側 3px `Teal` accent border。
    - `Invalid (驗證失敗)`：危險背景 + 左側 3px `Danger` accent border。
- [x] **達成率三態顯示**：
    - `< 80%`：紅色危險態。
    - `80% ~ 99%`：橙色警告態（新增 `.rate:not(.low):not(.high)` 規則）。
    - `≥ 100%`：綠色成功態。

## 階段 4：輸入元件與互動細節 (Interactions) ✅ DONE
**目標：減少輸入錯誤，增加操作流暢度。**

- [x] **輸入框樣式 (Input Styling)**：
    - 隱藏 number 輸入框的上下箭頭 (spinner)。
    - Focus 時使用 `--accent-ring` (Teal 色環)。
    - 數量輸入框 (Quantity) 已實作「點擊即選中」邏輯 (`focus → select()`)。
- [x] **微動畫 (Micro-animations)**：
    - 總額變動時的 `flash` 動畫升級為三階段 (scale 1.08 → 1.02 → 1)。
    - 新增 `save-pulse` 動畫用於儲存狀態指示器的淡入效果。

## 階段 5：全域拋光與驗證 (Polish & Verification)
**目標：確保不同解析度與邊界狀況下的視覺一致性。**

- [ ] **響應式適配**：確保在不同筆電螢幕下，表格欄位不會過度壓縮。
- [ ] **瀏覽器檢查清單**：完成 `docs/workflows/local-setup.md` 中的瀏覽器驗證項。

---

## 執行順序與優先級
1. ~~**立即執行**：階段 1 (CSS Tokens) & 階段 2 (Layout)。~~ ✅ 已完成 (2026-05-02)
2. ~~**重點執行**：階段 3 (Table Grid)。~~ ✅ 已完成 (2026-05-02)
3. ~~**後續拋光**：階段 4 (Interactions)。~~ ✅ 已完成 (2026-05-02)
4. **最終驗證**：階段 5 (Polish & Verification)。 ← 下一步
