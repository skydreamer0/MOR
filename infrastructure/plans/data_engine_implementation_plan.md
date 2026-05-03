# MOR 決策輔助資料引擎 (Data Engine) 實作計畫

此計畫接續前期的 UI 重構與預算匯入，專注於將「過去 6 個月的歷史銷售」與「上月達成表現」整合至工作台中，完成 **「辨識 ➔ 回顧 ➔ 現況 ➔ 決策」** 的左至右視覺動線。

---

## 階段一：擴充資料模型 (Data Models)
**目標：在核心資料結構中預留空間，存放歷史與趨勢資料。**
1. **修改 `src/backend/forecast_models.py`**
   - 擴充 `ForecastRow`，新增以下屬性：
     - `last_month_actual: float = 0.0` (上月實際銷量)
     - `last_month_budget: float = 0.0` (上月預算目標)
     - `trend_6m: list[float] = None` (過去 6 個月的歷史銷量陣列，例如 `[10, 12, 15, 10, 20, 18]`)
   - （可選）新增 `avg_3m: float = 0.0` 作為近期動能參考。

## 階段二：後端資料撈取與聚合 (Data Aggregation)
**目標：從 `mor_workbench.db` 的 `sales_records` 與 `budget_targets` 中高效撈出資料。**
1. **實作查詢邏輯 (`src/backend/database.py` 或獨立的 `history_service.py`)**
   - **上月資料**：給定當前預估月份 (例如 2026 年 5 月)，推算出上個月 (2026 年 4 月)，並寫入 SQL 查詢 `sales_records` 中各醫院與品項的總銷量。
   - **半年趨勢**：寫入 `GROUP BY year, month, customer_name, product_code` 的 SQL，撈出 Month-6 到 Month-1 的逐月銷量，並在 Python 端對齊為長度 6 的陣列（若該月無銷量補 0）。
2. **整合至預估引擎 (`src/backend/app.py` 或 `forecast_engine.py`)**
   - 在 `build_forecast` 產生初步預估後，透過新寫好的查詢服務，將上述資料「批量 (Batch)」灌入 `ForecastRow`，避免 N+1 查詢效能問題。

## 階段三：前後端資料傳遞 (Presenter)
**目標：將後端算好的陣列資料轉換為前端可讀的格式。**
1. **修改 `src/backend/web/forecast_presenter.py`**
   - 在序列化 (Serialization) 邏輯中，將 `trend_6m` 轉換為 JSON 格式字串或陣列。
   - 計算 `last_month_gap` (上月實際 - 上月預算) 並一併傳遞。

## 階段四：前端 UI 視覺化 (Frontend Visualization)
**目標：將冷冰冰的數字轉化為一眼看懂的趨勢圖與顏色。**
1. **修改 `templates/index.html`**
   - 依照「黃金三階段」重新排序 Table 欄位 (回顧 ➔ 現況 ➔ 決策)。
   - **上月表現區塊**：利用紅綠兩色顯示上月的達成率。若低於 80% 顯示紅色警告，幫助業務判斷本月是否需要補業績。
   - **自然 GAP 區塊**：即時顯示「系統基準預估」與「下月預算」的差距。
2. **導入微型趨勢圖 (Sparkline)**
   - 在每一列使用簡單的 HTML Canvas 或內聯 SVG 技術，將 `trend_6m` 的陣列繪製為小型折線圖。
   - 視覺規範：不需 X/Y 軸，只需單純的走勢線，最後一個點加深顏色代表上個月的落點。

---

## 執行順序建議
1. 優先執行 **階段一與階段二**，確保 `app.py` 能成功印出帶有趨勢陣列的資料。
2. 確認後端效能不受影響（< 1.5 秒）後，再進入 **階段三與四** 進行前端畫面排版。
