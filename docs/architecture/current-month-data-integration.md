# 當月業績資料整合架構

## 背景

系統使用兩種業績資料來源，各有不同的更新頻率與生命週期：

| 來源 | 格式 | 涵蓋範圍 | 更新時機 |
|---|---|---|---|
| `業績明細*.xlsx` | 業績明細工作表（年/月/日 三欄） | 歷史全期（例如 2024-01 起） | 每月底確定後一次性更新 |
| `SHPB202.xlsx`（或同格式） | 出貨日期單欄（YYYYMMDD）+ 產品/數量 | 當月累積，持續變動 | 使用者隨時上傳最新版 |

月底業績明細更新後，當月資料進入歷史紀錄，SHPB 資料即自動失效。

## 資料流

```
[業績明細 Excel]  ──sync──▶  sales_records (DB)
                                    │
[SHPB Excel]  ──upload──▶  current_month_records (DB)
                                    │
                              load_sales_detail()
                              (合併兩個來源)
                                    │
                            forecast_engine (計算周期/預估)
```

## 設計決策

### 為何用獨立的 `current_month_records` 表，而非直接寫入 `sales_records`？

- **歷史資料零風險**：SHPB 的當月資料不會污染歷史月份
- **重複上傳安全**：每次上傳只刪除並取代當月，不影響其他月份
- **月底自動失效**：sync 時若業績明細已涵蓋該月，自動清空當月記錄，無需手動處理
- **易 rollback**：若 SHPB 資料有誤，清空 `current_month_records` 即可回到純歷史視角

### 時間不重疊保證無衝突

業績明細只包含「已確定的歷史月份」，SHPB 只包含「目前尚未確定的當月」。
兩者在時間上天然不重疊，合併時不會產生重複資料。

## 資料表結構

### `current_month_records`

欄位與 `sales_records` 相同，另加：
- `imported_at TIMESTAMP`：最後一次上傳的時間，方便 debug 確認資料新鮮度

### SHPB 欄位對應

| SHPB 欄位 | 對應至 | 備註 |
|---|---|---|
| `出貨日期` | `order_date` | 格式 YYYYMMDD，需轉換 |
| `客戶簡稱` | `customer_name` | 直接使用 |
| `產品` | `product_code` | 同 normalize_product_code |
| `產品簡稱` | `product_name` | 直接使用 |
| `銷售數量` + `贈品數量` | `quantity` | 相加，與業績明細「銷+贈S量」語意一致 |
| `銷貨淨價` | `unit_price` | |
| `含稅淨額` | `amount` | |

## 月底清理邏輯

`sync_excel_to_db` 執行後，讀取 `sales_records` 的最新年月，
清除 `current_month_records` 中所有 `(year, month) <=` 該月的資料。

這樣月底 sync 後，使用者不需要手動清理任何東西。

## 相關程式碼

- `src/backend/database.py` — `current_month_records` 表定義
- `src/backend/etl.py` — `normalize_shpb_records()`, `import_current_month()`
- `src/backend/data_loader.py` — `load_sales_detail()` 合併邏輯
- `src/backend/app.py` — `POST /upload/current-month` 路由（Stage 4）
