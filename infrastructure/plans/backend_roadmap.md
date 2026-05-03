# MOR Backend Roadmap (業務資料支撐藍圖)

此藍圖專注於提供前端「決策動線」所需的精確歷史與預算資料，並確保計算效能與系統穩健性。

## Phase 1: 決策輔助資料引擎 (Decision Context Data)
**目標：為前端的「回顧過去」與「現況」模組提供必要數據。**
- [ ] **上月表現計算 (Last Month Performance)**：
  - 開發邏輯取得 Month-1 的「實際銷售量」與 Month-1 的「預算目標」。
  - 計算出 Month-1 的 GAP，供前端顯示。
- [ ] **半年趨勢陣列 (6-Month Trend Array)**：
  - 在 `forecast_engine.py` 或 ETL 層，聚合每個 (醫院, 品項) 組合過去 6 個月的歷史銷售數字。
  - 將這 6 個數字作為一個 Array 封裝入 `ForecastRow`，供前端渲染 Sparkline 使用。
- [ ] **效能優化**：因需要跨月份撈取資料，需確保 DataFrame 的彙整與 SQLite 的查詢在合理時間 ( < 1.5s ) 內完成。

## Phase 2: 快照與版本控制系統 (Versioning System)
**目標：將目前的「草稿」狀態固化為「定稿」紀錄。**
- [ ] **快照寫入邏輯**：
  - 實作儲存快照的業務邏輯，將當下所有的 `系統預估`、`人工調整`、`最終預估` 寫入 `forecast_snapshots` 與 `snapshot_items` 表格。
- [ ] **版本鎖定機制**：
  - 若該月份已經標記為「已定稿 (Finalized)」，則 API 拒絕任何 `/adjustments/save` 的寫入請求。

## Phase 3: 準確度回測引擎 (Backtesting Engine)
**目標：自動評估過去預估的品質。**
- [ ] **回測計算腳本**：
  - 當匯入新的 `業績明細` 後，自動與上個月的「定稿快照」進行比對。
  - 計算誤差指標 (例如 MAPE)，並寫入 `accuracy_reports` 資料表，供後續分析查詢。

## Phase 4: ETL 穩健化與自動化 (ETL Robustness)
**目標：防禦髒資料，確保同步過程不中斷。**
- [ ] **檔案格式驗證**：在解析 Excel 之前，嚴格驗證必要欄位與 Sheet (如 `07預算S總量`) 是否存在。
- [ ] **異常紀錄與警報**：若遇無法對應的「商品號」或「醫院名稱」，略過並記錄至日誌，最終產出同步報告。
