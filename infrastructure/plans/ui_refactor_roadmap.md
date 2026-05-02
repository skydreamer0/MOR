# MOR UI Refactor Roadmap (專項改善計畫)

本計畫旨在將 MOR 的介面從基礎原型提升至 **「現代化數據工作台 (Modern Data Workbench)」** 等級，對齊 Tier-1 企業內部工具標準。

## 核心目標
1. **提升專業感**：引入更精緻的色彩、字體與間距系統。
2. **強化操作效率**：優化高密度表格的掃描性與數據對比度。
3. **即時狀態感知**：確保手動調整與系統預估的區隔清晰直覺。

---

## 階段 1：基礎設計系統與 Token (Foundation)
**目標：建立可維護的 CSS 變數系統。**

- [ ] **顏色系統 (Color Palette)**：
    - 引入更深邃的 `Slate Gray` 作為中性背景。
    - 精確定義 `Teal-600` 作為品牌主色，並提供 Hover 與 Active 狀態。
    - 優化 `Success`, `Warning`, `Danger` 的背景與文字對比。
- [ ] **字體系統 (Typography)**：
    - 預設使用 `Inter` (數字) 與 `Microsoft JhengHei` (中文) 的組合。
    - 建立微縮字級規範 (12px, 13px, 14px)，適配高密度作業。
- [ ] **空間系統 (Spacing)**：
    - 統一使用 4px 為基數的 Padding/Margin 規範。

## 階段 2：佈局元件重構 (Layout Components)
**目標：釋放垂直空間，優化工作流。**

- [ ] **精簡導覽列 (Sticky Header)**：
    - 縮小標題高度，優化年份/月份切換器的視覺權重。
- [ ] **指標卡片區 (Metric Summary)**：
    - 從邊框卡片改為「無邊框/淺背景」設計，提升數據的可讀性。
    - 加入數值單位的視覺縮放。
- [ ] **吸附式動作條 (Fixed Bottom Bar)**：
    - 優化陰影效果，確保與表格內容有清晰的深度層次。

## 階段 3：核心數據表格優化 (Data Grid Deep-dive)
**目標：達成 spreadsheet-native 的極致體驗。**

- [ ] **表頭與對齊 (Header & Alignment)**：
    - 強化 `Sticky Header` 的陰影與分隔線。
    - 確保金額與數量嚴格右對齊（使用 Tabular Numbers）。
- [ ] **狀態標記與 Badge**：
    - 重設計 `本月跳單` 與 `未到週期` 的標籤，使其不干擾視線。
- [ ] **互動列狀態 (Row States)**：
    - 實作更明顯的 `Hover` 與 `Selected` 效果。
    - 優化 `Excluded (已排除)` 的「半透明灰掉」效果。
    - 強化 `Edited (已手動調整)` 的背景高亮。

## 階段 4：輸入元件與互動細節 (Interactions)
**目標：減少輸入錯誤，增加操作流暢度。**

- [ ] **輸入框樣式 (Input Styling)**：
    - 移除笨重的邊框，改用 Focus 時的藍色環 (Focus Ring)。
    - 針對數量輸入框 (Quantity) 實作微型的「點擊即選中」邏輯。
- [ ] **微動畫 (Micro-animations)**：
    - 當總額變動時，加入輕微的數值滾動或漸變動畫。

## 階段 5：全域拋光與驗證 (Polish & Verification)
**目標：確保不同解析度與邊界狀況下的視覺一致性。**

- [ ] **響應式適配**：確保在不同筆電螢幕下，表格欄位不會過度壓縮。
- [ ] **瀏覽器檢查清單**：完成 `docs/workflows/local-setup.md` 中的瀏覽器驗證項。

---

## 執行順序與優先級
1. **立即執行**：階段 1 (CSS Tokens) & 階段 2 (Layout)。
2. **重點執行**：階段 3 (Table Grid)。
3. **後續拋光**：階段 4 & 5。
