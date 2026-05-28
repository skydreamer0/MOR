# ADR-003: 轉向 SQLite 資料庫架構

## 1. 背景 (Context)
目前 MOR 系統直接讀取 `業績明細.xlsx` 等三個 Excel 檔案。隨著功能增加，面臨以下挑戰：
- **效能問題**：每次請求都要讀取數百 KB 的 Excel 並進行 Pandas 分組計算，反應速度較慢。
- **持久化困難**：人工調整（Manual Overrides）與品項排除（Exclusions）目前使用 JSON 或臨時狀態儲存，容易遺失或難以維護。
- **資料整合**：現有三個檔案（明細、三年報表、預算）格式不一，在 Pandas 中進行跨表 Join 邏輯複雜。

## 2. 決策 (Decision)
引入 **SQLite** 作為核心存儲引擎，並建立自動化 ETL 流程。

### 核心架構變化：
1. **資料層 (Storage)**：
   - 使用 `mor_workbench.db` (SQLite)。
   - `pandas` 將作為 ETL 工具與 SQL 查詢的封裝層，不再直接作為主要的資料持有者。
2. **ETL 流程 (Sync)**：
   - 提供「同步資料 (Sync)」功能，一次性解析三個 Excel 並寫入資料庫。
3. **功能增強**：
   - **人工調整持久化**：使用者在介面輸入的數量會直接存入資料庫，重新整理頁面也不會消失。
   - **多維度對照**：預測邏輯可以直接在 SQL 層級整合「去年同期」、「上月實績」與「預算目標」。

## 3. 資料庫 Schema 設計 (Proposed Schema)

### `sales_records` (銷售紀錄)
- `id` (PK)
- `order_date` (日期)
- `customer_name` (客戶簡稱)
- `product_code` (商品號)
- `product_name` (商品名稱)
- `quantity` (數量)
- `unit_price` (單價)

### `item_configs` (品項設定)
- `product_code` (PK)
- `is_excluded` (是否排除, 0/1)
- `custom_category` (自定義分類)

### `forecast_adjustments` (預估調整)
- `year`, `month`, `customer_name`, `product_code` (Composite PK)
- `manual_quantity` (人工輸入數量)
- `adjustment_reason` (調整原因)
- `updated_at` (最後更新時間)

### `budget_targets` (預算目標)
- `year`, `month`, `customer_name`, `product_code` (Composite PK)
- `target_quantity` (預算數量)

## 4. 實作計畫 (Implementation Plan)
1. **Phase 1**: 建立 `src/backend/database.py` 處理連線與初始化。
2. **Phase 2**: 實作 `src/backend/etl.py` 將現有三個檔案匯入。
3. **Phase 3**: 修改 `ForecastEngine` 改為讀取 SQL。
4. **Phase 4**: 實作 AJAX 介面，讓人工調整能即時存入 DB。

---
> [!NOTE]
> 採用此方案後，Excel 將轉變為「原始資料來源」，而資料庫則是「營運工作台」的核心。
