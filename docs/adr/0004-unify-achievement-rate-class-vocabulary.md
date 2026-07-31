# ADR-0004: 統一達成率 class 詞彙

## 狀態 (Status)
Accepted — 2026-08-01（對應 `ROADMAP_FRONTEND.md` FE-9）

## 1. 背景 (Context)

「預算達成率」是 MOR 全站共用的四階語意：

| 階 | 門檻 | 意義 | 色 |
|---|---|---|---|
| 1 | >= 100 | 達成 | 綠 (`--success-text`) |
| 2 | 90–99 | 警戒 | 橙 (`--accent-2`) |
| 3 | 80–89 | 注意 | 棕 (`--warning-text`) |
| 4 | < 80 | 未達 | 紅 (`--danger`) |

同一組語意卻長出三套互不相通的 class 詞彙：

| 來源 | 詞彙 |
|---|---|
| `static/js/analytics-renderer.js` `_rateCls()` | `positive / warning / caution / negative` |
| `templates/_value_macros.html` `achievement()` | `success-text / rate-warning / caution-text / danger-text` |
| `static/js/forecast-table.js` `updateRateElement()` | `low / high`（只有二階，90–99 與 80–89 看不出來） |

後果：`mor.css` 中同一組「四階 → token」映射被展開六次（920 / 1077 / 1136 /
1208 / 1229 / 1741 行附近），Forecast 頁與其他頁的達成率顯示不一致，
新增頁面時開發者無從判斷該用哪一套。

## 2. 決策 (Decision)

**正典詞彙定為 `positive / warning / caution / negative`。**

理由：
1. 已經是四階，不需要為了統一而新造名稱。
2. 語意中性——描述的是「這個數字好不好」，而不是「該塗什麼顏色」，
   顏色留給 `mor.css` 的 token 決定。
3. 已經是 `fmt.js` `budgetRate()` 的輸出，也是 `analytics-renderer.js`、
   `analytics-table.js` 的既有詞彙，改動面最小。

配套：

- `static/css/mor.css` 以 `.positive` / `.warning` / `.caution` / `.negative`
  四條全域規則作為**唯一正典定義**。
- 舊名稱 `success-text` / `rate-warning` / `caution-text` / `danger-text`
  **保留為 CSS alias**，指向完全相同的 token，並在檔案中註明其為 legacy alias。
- `templates/_value_macros.html` 的 `achievement()` 改為輸出正典 class。
- `static/js/forecast-table.js` `updateRateElement()` 改用 `AnalyticsFmt.budgetRate()`
  輸出正典 class，`.rate.low` / `.rate.high` 二階規則移除（FE-8）。
- 門檻常數只留 `fmt.js` 的 `BUDGET_RATE_ACHIEVED / _WARNING / _CAUTION` 一份（FE-10）。

## 3. 為什麼保留 alias 而不是全面改名 (Rationale)

`success-text` 等舊 class 並非只透過 macro 產生，而是被 **多個樣板直接寫死**，
例如 `templates/_monthly_review_insights.html`、`templates/product_monitor.html`；
其中有些用途根本不是達成率（例如 `accuracy()` 的 95/85 兩階門檻、
`cycle_status == 'delayed'`、`projection_confidence`）。

全面改名會變成跨十餘個樣板的大範圍重構，違反主 ROADMAP 的
「不做大範圍重構，一次收一個接縫」原則，且會把「達成率語意」與
「其他剛好同色的語意」混為一談。因此本次只收斂**產生達成率 class 的三個出口**，
舊名稱以 alias 續存。

## 4. 後果 (Consequences)

- 新程式碼一律使用正典四階；舊名稱可用但不應新增使用點。
- alias 是技術債，但是**有界的**技術債：只要出口統一，之後要逐頁改名隨時可做，
  且不會再有新的分歧產生。
- `mor.css` 中六處重複的四階映射可在 FE-16 一併收斂到正典規則（本 ADR 未做）。
- `.positive` 等四條全域規則帶 `!important`，沿用它們取代的 legacy alias 的既有行為，
  以蓋過表格／儲存格的繼承色。
