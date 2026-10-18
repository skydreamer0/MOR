# 合成資料練習與操作截圖

[返回 README](../../README.md) · [使用指南](user-guide.md)

此範例完全使用虛構客戶、商品與數字，不取自公司工作簿。請在獨立資料目錄練習，勿對正式資料庫重播範例。

## 建立練習檔案

完成 README 的相依套件安裝後，在專案根目錄把下列內容另存為 `demo_workbooks.py`，用同一 Python 環境執行。程式只建立新的 `mor-demo-inputs` 目錄；目錄已存在時會停止，避免覆寫舊檔。這是練習腳本，不必提交產生的工作簿或資料庫。

```python
from pathlib import Path
import pandas as pd

out = Path("mor-demo-inputs")
out.mkdir(exist_ok=False)

labels = ["01銷+贈量", "02銷+贈S量", "03銷含稅總額", "04銷未稅總額", "05折後業績額"]
monthly = pd.DataFrame([
    {"客戶簡稱": "示範客戶甲", "商品號": "DEMO-001", "標  題": label, 202501: value}
    for label, value in zip(labels, [2, 20, 100, 95, 90])
])
budget = pd.DataFrame([
    {"客戶簡稱": "示範客戶甲", "商品號": "DEMO-001", "標  題": label, 202501: value}
    for label, value in [("02預算總量", 3), ("07預算S總量", 30), ("04預算總額", 150)]
])

def save(name, frames):
    with pd.ExcelWriter(out / name, engine="openpyxl") as writer:
        pd.DataFrame({"說明": ["虛構教學資料，不含公司資料"]}).to_excel(
            writer, sheet_name="說明", index=False)
        for sheet, frame in frames:
            frame.to_excel(writer, sheet_name=sheet, index=False, startrow=3, startcol=2)

save("demo-combined.xlsx", [("實績範例", monthly), ("預算範例", budget)])
save("demo-monthly-only.xlsx", [("另一個表名", monthly)])
save("demo-budget-only.xlsx", [("目標", budget)])
conflict = monthly.copy()
conflict.loc[conflict["標  題"] == "02銷+贈S量", 202501] = 21
save("demo-monthly-conflict.xlsx", [("衝突範例", conflict)])

daily = pd.DataFrame([{
    "出貨日期": 20260115, "客戶代號": "DEMO-C002", "客戶簡稱": "示範客戶乙",
    "產品": "DEMO-002", "產品簡稱": "示範商品乙", "銷售數量": 2, "贈品數量": 1,
    "銷貨淨價": 10, "含稅淨額": 30, "折後業績": 28,
    "發票編號": "DEMO-I001", "出貨單號": "DEMO-S001", "單別": "normal", "業績屬性": "normal",
}])
save("demo-daily.xlsx", [("每日示範", daily)])
print(out.resolve())
```

每個資料表的標題位於 C4；第一張工作表只有說明文字。這讓你驗證辨認不依賴第一張表、固定表名或 A1 標題位置，不表示支援任意轉置。

## 使用獨立資料啟動

先停止原本練習用的 MOR。於專案根目錄將以下另存為 `demo_server.py`，用同一 Python 環境執行：

```python
from pathlib import Path
from src.backend.app import create_app

data = Path("mor-demo-data").resolve()
data.mkdir(exist_ok=True)
app = create_app({"DATA_BASE_PATH": data, "DB_BASE_PATH": data})
app.run(host="127.0.0.1", port=5001, debug=False, use_reloader=False)
```

開啟 http://127.0.0.1:5001/settings。這個範例只使用 `mor-demo-data`，不讀正式 Excel；輸入檔另外放在 `mor-demo-inputs`，只從檔案選擇器上傳指定檔案。再次啟動會保留同一份練習資料，不會自動重置。需全新情境時另取新的練習資料目錄名稱，不要刪正式資料。

## 按情境練習

### 單檔、多工作表

1. 選 `demo-combined.xlsx`，先不填涵蓋月份，按預覽。
2. 預期辨認月實績 5 筆指標欄值與預算 3 筆；提示需明確指定已觀察月份，不寫資料。
3. 回設定頁，重新確認檔案，填月實績月份 `2025-01`，預覽應可提交。
4. 匯入後預期月彙總頁顯示「示範客戶甲／DEMO-001」，五欄為 `2`、`20`、`100`、`95`、`90`。日預測不可用的說明應可見。

### 多檔合併

在另一個全新練習資料目錄啟動，選 `demo-monthly-only.xlsx` 與 `demo-budget-only.xlsx`，填 `2025-01`。預期得到與上方相同的月指標與預算。不要把合併檔和拆分檔全部選上，否則是重複資料情境。

### 重複與衝突

- 重送已成功匯入的 `demo-combined.xlsx`：現有值未變時應不增加交易或收據。
- 在同一批選 `demo-monthly-only.xlsx` 與 `demo-monthly-conflict.xlsx`，填 `2025-01`：同一月 S 量分別為 20 與 21，應拒絕整批；勾略過相同月指標也不能消除數值衝突。
- 上一項失敗後重新開啟月彙總頁，已提交的 S 量仍為 20；失敗不應留下部分變更。

### 每日用途

選 `demo-daily.xlsx`，按「匯入監控 SHPB」，到產品監控切換 `2026-01`。預期最新匯入批次摘要顯示 1 筆、數量 3（銷售 2 + 贈品 1）、金額 30。全新資料目錄只匯入監控 SHPB 時，不會產生個別客戶／商品的監控列；那些列來自真正的歷史／當月每日交易所建立的預估列。這一筆只驗證匯入批次摘要，不代表已建立叫貨週期或個別監控列。

若要練習「匯入當月 SHPB」，使用另一個全新練習資料目錄操作；不要把兩個用途當作同一份同步結果。

## 截圖拍攝清單

目前本文件提供可重現步驟，**尚未附上真實瀏覽器截圖**。下列是待拍清單，不是已通過的瀏覽器測試。不可用 HTML 回應、設計稿或生成圖片冒充實際操作截圖。

待有可用且授權的瀏覽器後，僅使用上述合成資料拍攝，建議同一個桌面視窗尺寸（例如 1440 × 1000），保持欄位與警告可讀。圖片儲存至 `docs/images/` 後，再補 Markdown 圖片連結與替代文字；不要先放破圖連結。

| 圖號／建議檔名 | 畫面與操作 | 畫面應能證明 |
| --- | --- | --- |
| 01 `import-settings.png` | `/settings` 展開匯入面板，選合成檔 | 三個匯入用途、月份範圍及完整取代警告 |
| 02 `import-preview.png` | 合併檔填 `2025-01` 後預覽 JSON | 來源表格／位置、5 與 3 指標筆數、`can_commit=true` |
| 03 `monthly-analysis.png` | 單檔提交後的 `/history/monthly/view` | 客戶／商品、五指標合計、日預測不可用 |
| 04 `multi-file-import.png` | 全新練習目錄選兩個分檔 | 多檔選擇與正確涵蓋月份；配合結果核對 |
| 05 `monthly-conflict.png` | 同批匯入兩個 S 量衝突檔 | 真實錯誤訊息，沒有靜默覆蓋 |
| 06 `monthly-after-rejection.png` | 錯誤後重開月彙總 | 原 S 量仍為 20，不宣稱只靠截圖驗證整個 DB 原子性 |
| 07 `daily-monitor.png` | 監控用途匯入後切 `2026-01` | 最新匯入批次摘要：1 筆、數量 3、金額 30；不要求出現個別監控列 |
| 08 `monthly-empty.png` | `/history/monthly/view?year=2025&month=2` | 沒資料與零實績明確不同 |

發布前檢查：每張圖記錄程式版本、日期、情境、預期／實際結果；人工檢視像素，確認無真實公司名稱、金額、使用者路徑、瀏覽器個人資訊或憑證。只有完成實際操作才標示通過；遮罩不能代替使用乾淨的合成資料環境。

## 文件寫法的參考

以下是寫作結構參考，不表示 MOR 已具備這些公司的產品功能：

- [GitHub：About READMEs](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes)：README 先回答用途、開始方式與求助入口，長篇內容另頁，使用相對連結。
- [Microsoft：Writing step-by-step instructions](https://learn.microsoft.com/en-us/style-guide/procedures-instructions/writing-step-by-step-instructions)：以任務命名短標題，先指出操作位置，以編號列出動作與完成步驟。
- [Stripe：Testing](https://docs.stripe.com/testing)：以安全測試資料區隔正式資料，提供成功與失敗情境；此文件據此安排重送、衝突與空月份範例。

此處為摘要與 MOR 實際應用，未複製大段原文。
