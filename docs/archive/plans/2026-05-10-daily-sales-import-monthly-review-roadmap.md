# MOR 每日業績匯入與月底檢討 Roadmap

## 目標

將 MOR 從「月底預估下個月」升級成完整的月度營運循環：

```text
月底預估下個月
→ 月中每日匯入當月累積業績
→ 依實績、出貨週期、預算與去年同期追蹤跳單
→ 月底結月與檢討
→ 回饋下次預估
```

此計畫先作為架構與實作順序討論稿，不代表一次全部實作。

## 已確認決策

- 每日業績檔是「當月份累積到匯入日」的完整快照，不是只含當天新增資料。
- 檔名不固定，後端只依欄位格式判斷，不綁定 `SHPB202.xlsx`。
- 匯入入口放在 `產品跳單監控` 頁。
- 匯入文案使用「選擇當月累積業績檔」，並提示「系統將依欄位格式判斷資料，不限制檔名。」
- 每次匯入同年月資料時，以最新版快照覆蓋同年月舊當月實績。
- 每日總結列忽略；必須有可解析的出貨日期、客戶簡稱、產品代碼才納入。
- 數量口徑：`銷售數量 + 贈品數量`。
- 金額口徑：`含稅淨額`。
- `折後業績` 先視為獎金計算基礎原始欄位，只存入資料庫，暫不顯示、不參與跳單或 GAP 計算。
- 台灣工作日需排除週六、週日與台灣國定假日，補班日算工作日。
- 工作日曆初版由系統抓取台灣公開辦公日曆資料並匯入 `workday_calendar`；缺資料時 fallback 為週一至週五。
- 產品跳單 UI 採漸進揭露：主表快速掃描，展開列看原因與細節。
- 風險門檻採 90/100 規則：
  - 90% 以下為高風險。
  - 90% 至 100% 為注意。
  - 100% 以上為正常。

## 資料模型方向

### daily_import_batches

記錄每次匯入行為，用於追蹤來源與檢核。

建議欄位：

```text
id
source_filename
source_hash
sales_year
sales_month
imported_at
row_count
date_start
date_end
quantity_total
taxed_amount_total
status
message
```

### daily_sales_actuals

保存當月最新版累積業績明細。初版採「同年月覆蓋」策略。

建議欄位：

```text
id
sales_year
sales_month
sales_date
customer_code
customer_name
product_code
product_name
sales_quantity
gift_quantity
actual_quantity
net_unit_price
taxed_amount
bonus_basis_amount
invoice_number
shipment_number
order_type
performance_type
import_batch_id
```

### workday_calendar

提供出貨週期、已過工作日、全月工作日的共同基準。

建議欄位：

```text
date
is_workday
holiday_name
source
note
```

### month_close_records

保留未來結月狀態，避免月底完整資料被後續誤覆蓋。

建議欄位：

```text
year
month
closed_at
source_batch_id
actual_row_count
actual_quantity_total
actual_amount_total
note
```

## Phase 1：每日業績匯入基礎

目標：讓當月累積業績檔正式進 DB，產品跳單頁可以讀到最新當月實績。

範圍：

- 在 `產品跳單監控` 頁新增匯入區塊。
- 新增匯入後端流程，讀取每日業績 Excel。
- 驗證必要欄位。
- 忽略總結列與不完整列。
- 建立 `daily_import_batches` 紀錄。
- 覆蓋同年月舊 `daily_sales_actuals`。
- 寫入新明細。
- 顯示匯入結果：年月、日期範圍、筆數、數量合計、含稅淨額合計。

不做：

- 不保留每次匯入的完整歷史明細版本。
- 不做多使用者資料隔離。
- 不使用檔名決定格式。

## Phase 2：台灣工作日曆與週期基礎

目標：讓出貨週期與月底推估使用同一套工作日邏輯。

現況：

- 現有 forecast engine 已有日曆天 `cycle_days`、`next_order_date`、近月平均等雛形。
- 尚未使用台灣工作日，也尚未接入每日當月實績。

範圍：

- 新增 `workday_calendar`。
- 新增台灣公開辦公日曆抓取與匯入流程，由系統處理資料來源，不要求使用者手動整理工作日曆。
- 新增工作日計算服務：
  - 兩日期間工作日數。
  - 當月已過工作日。
  - 當月總工作日。
  - 月底剩餘工作日。
- 若工作日曆缺資料，fallback 週一至週五。

## Phase 3：產品跳單監控 v2

目標：讓主表快速回答「誰有問題、問題在哪、要不要追」。

主表欄位：

```text
狀態
客戶
品項
最近出貨日
距最近出貨工作日
本月目前數量
推估月底數量
最終預估
去年成長率
預算達成率
週期狀態
```

展開列內容：

```text
風險摘要
狀態原因
建議追蹤動作
數量比較
金額比較
週期分析
```

比較軸：

```text
最新落點 vs 最終預估
最新落點 vs 去年同期
最新落點 vs 本月預算
```

狀態邏輯：

```text
高風險：
- 去年成長率 < 90%
- 或預算達成率 < 90%
- 或距最近出貨工作日 > 歷史平均週期 * 1.2

注意：
- 去年成長率 >= 90% 且 < 100%
- 或預算達成率 >= 90% 且 < 100%
- 或距最近出貨工作日 >= 歷史平均週期 * 0.8

正常：
- 去年成長率 >= 100%
- 預算達成率 >= 100%
- 出貨週期未接近延遲
```

後端可保留 `critical` severity，但主表只顯示「高風險」。

排序：

```text
1. severity
2. 預算達成率最低
3. 去年成長率最低
4. 距最近出貨工作日最高
```

## Phase 4：品項落點推估模型

目標：避免用粗糙的工作日比例外推客戶品項金額與數量。

初版策略：採「人工輔助 + 中等模型提示」。系統提供建議落點、可能再出貨次數、典型單次出貨量、信心程度與狀態原因，但不覆蓋既有 `最終預估`。

方向：

```text
月底推估數量 =
本月目前數量
+ 依客戶品項歷史出貨週期推估的剩餘可能出貨數量
```

需要計算：

- 同客戶 + 同品項的歷史平均出貨週期，使用工作日。
- 歷史典型單次出貨量。
- 本月最近出貨日。
- 月底前可能再出貨次數。
- 剩餘可能出貨數量。
- 推估月底數量。
- 推估月底金額。

金額推估：

- 本月目前金額使用 `含稅淨額`。
- 推估剩餘金額應依品項單價或近期待用含稅單價，不使用 `折後業績`。
- 去年同期金額若歷史資料有可對應欄位才顯示，沒有顯示 `-`。
- 本月預算金額使用 `budget_targets.target_amount`。

## Phase 5：三軸比較與預估回饋

目標：同一列同時知道預估準不準、是否成長、是否達標。

數量比較：

```text
本月目前數量
推估月底數量
最終預估數量
vs 最終預估 GAP
去年同期數量
去年成長率
vs 去年同期 GAP
本月預算數量
預算達成率
vs 預算 GAP
```

金額比較：

```text
本月目前含稅淨額
推估月底金額
最終預估金額
去年同期金額
本月預算金額
金額 GAP
```

最終預估定義：

```text
若有人工調整，採人工調整。
若沒有人工調整，採系統預估。
```

## Phase 6：結月流程

目標：月底完整資料匯入後，將當月實績鎖定成正式歷史，供後續週期、同期、檢討使用。

初版策略：結月後先保留獨立 actuals 表，查詢時與既有 `sales_records` 合併；暫不直接併入 `sales_records`，避免新舊來源口徑混在一起後難以拆分。

流程：

```text
匯入當月完整累積業績
→ 使用者檢查筆數與合計
→ 按「結月」
→ 鎖定該年月 actuals
→ 寫入或同步正式歷史資料
→ 月底檢討頁可使用該月結果
```

結月後需要避免：

- 同年月資料被誤覆蓋。
- 未確認資料直接成為正式歷史。
- forecast 準確度回測基準改變。

## Phase 7：月底檢討頁

目標：月結後回答「這個月做得怎樣」與「下次怎麼估更準」。

初版策略：數量比較優先完整實作；金額只顯示可靠口徑。若去年同期金額或最終預估金額缺少可靠來源，顯示 `-`，不使用錯口徑硬補。

建議獨立頁：

```text
/monthly-review
```

頁面區塊：

```text
月度總覽
- 實際數量 / 金額
- vs 最終預估
- vs 預算
- vs 去年同期

預估準確度
- 高估最多品項
- 低估最多品項
- 預估命中率
- 誤差排行

跳單與成長
- 低於去年同期品項
- 高於去年同期品項
- 低於預算品項
- 超過預算品項

週期變化
- 出貨週期拉長
- 出貨週期縮短
- 本月未出貨但歷史應該出貨

下月預估提示
- 建議關注客戶品項
- 可能回補品項
- 可能持續跳單品項
```

頁面定位：

```text
Dashboard：看今天狀態。
產品跳單監控：月中追蹤與處理。
月底檢討：月結後復盤與學習。
```

## 建議實作順序

1. Phase 1：每日業績匯入基礎。
2. Phase 2：台灣工作日曆與工作日服務。
3. Phase 3：產品跳單監控 v2 UI 與狀態原因。
4. Phase 4：品項落點推估模型。
5. Phase 5：三軸比較與預估回饋。
6. Phase 6：結月流程。
7. Phase 7：月底檢討頁。

每個 Phase 應拆成可獨立驗證的小任務，不一次大改整個 forecast 流程。

## 可能影響檔案

```text
src/backend/database.py
src/backend/etl.py
src/backend/daily_sales_importer.py
src/backend/workday_calendar.py
src/backend/operational_views.py
src/backend/app.py
templates/product_monitor.html
static/js/monitor-table.js
tests/test_etl.py
tests/test_daily_sales_importer.py
tests/test_workday_calendar.py
tests/test_app.py
docs/workflows/operational-interface.md
ROADMAP.md
```

## 已確認的第一版取捨

1. 品項落點推估初版採人工輔助加中等模型提示。
2. `結月` 後先保留獨立 actuals 表，查詢時與 `sales_records` 合併。
3. 月底檢討頁第一版以數量為主，金額只顯示可靠欄位。
4. 台灣工作日曆由系統抓取官方公開資料並處理匯入；使用者不需要手動整理。
