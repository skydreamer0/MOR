# MOR — 月度業績預估工具

MOR 是本地端的業績工作台：匯入 Excel 歷史明細、月實績與預算，查看月度表現；有每日交易時，再估算客戶／商品需求、調整預估並匯出 Excel。

**只有月彙總也能查看月分析，但不能計算訂單日期、單價或叫貨週期，也不會自動建立每日預估列。**

## 從這裡開始

- 第一次使用：[安裝與啟動](#安裝與啟動)
- 要匯入報表：[匯入與日常操作指南](docs/workflows/user-guide.md)
- 要核對 Excel 欄名、月份與單位：[格式與安全契約](docs/workflows/workbook-import.md)
- 要用假資料練習：[合成資料範例與截圖清單](docs/workflows/demo-and-screenshots.md)
- 要維護程式：[架構與開發導覽](docs/architecture/overview.md)、[AGENTS.md](AGENTS.md)、[ROADMAP.md](ROADMAP.md)

## 安裝與啟動

需要 Python 3.10+；Windows 是主要使用平台。先下載／解壓原始碼，在包含 `app.py` 與 `requirements.txt` 的 MOR 目錄開啟終端機。

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

### macOS / Linux

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
```

開啟 http://127.0.0.1:5000/settings，展開「匯入報表（單檔或多檔）」。保持終端機開啟，結束時按 Ctrl+C。原始碼啟動入口啟用 Flask debug，只用於可信任的本機環境；不要對外開放或當作正式服務部署。

## 完成第一次匯入

1. 在「報表檔案」選擇一份或多份 `.xlsx`。可合併歷史／預算於一個工作簿的不同表格，也可分檔。
2. 選「預覽歷史／預算匯入」。目前預覽會顯示 JSON，檢查辨認類型、年月、筆數、來源位置，以及 `unresolved`。
3. 回設定頁，重新確認或選取檔案。月實績需填「月實績確實涵蓋月份」，例如 `2025-01`。預算月份僅寫 `1` 至 `12` 且表內無年份時，需填「預算年份」。
4. 再次預覽；確認 `can_commit` 為 `true`，再按「匯入歷史／預算」。預覽本身不儲存資料，提交時仍會重新檢查。
5. 月實績匯入後會開啟「月彙總實績」，核對客戶／商品及五種指標合計。其他歷史／預算匯入會返回總覽。

**「完整取代的每日月份」會刪除該月份新檔沒有列出的舊每日資料。** 除非你確定檔案含該月所有客戶、商品與交易，否則留白。第一次練習請使用[合成資料與獨立資料目錄](docs/workflows/demo-and-screenshots.md)。

## 可以做什麼

| 工作 | 入口 | 需要的資料 |
| --- | --- | --- |
| 查看月彙總、切換已匯入月份 | `/history/monthly/view` | 月實績五種指標 |
| 查看業績總覽 | `/` | 已匯入的適用來源與預算 |
| 調整預估、備註、停用品項、存草稿／定稿快照 | `/forecast` | 真正每日交易；月資料可補充月比較 |
| 匯入每日監控、追蹤跳單與月底推估 | `/monitor/products` | 完整監控 SHPB 欄位 |
| 管理品項規則與資料檢核 | `/settings` | 已匯入資料 |
| 比較結月實績、預估、預算與同期 | `/monthly-review` | 結月紀錄與適用來源 |

預估匯出 Excel 包含「預估總覽」「預估明細」「排除明細」。詳見[日常操作](docs/workflows/user-guide.md#調整預估與結月檢討)。

## 資料安全與限制

- 檔名不決定報表類型。依精確欄名辨認工作表／表格，不支援任意轉置或猜測合併標題。
- 月實績、每日資料同範圍不相加、不猜優先權。已結月月份禁止覆蓋。
- 整批驗證成功才寫入；失敗會回滾該次交易。這不等於已成功匯入後可按一下復原。
- 客戶代號／簡稱衝突會停止，沒有自動合併或身份修正工具。
- 工作簿是原始輸入，不會被匯入器覆寫。資料庫保存來源雜湊與位置，不代替原檔備份。
- 請勿把真實客戶資料、業績 Excel、資料庫或含私人數字的截圖提交至公開儲存庫。

問題排除與備份：[操作指南](docs/workflows/user-guide.md#排除匯入問題)。

## 套裝版本與資料位置

如使用 GitHub Releases 的 Windows／macOS ZIP，解壓後啟動套裝程式；套裝不含個人 Excel 或 SQLite 資料。執行資料位於：

- Windows：`%LOCALAPPDATA%\MOR`（依執行環境亦可能使用 `%APPDATA%\MOR`）
- macOS：`~/Library/Application Support/MOR`
- Linux 套裝：通常為 `~/.local/share/MOR`
- 原始碼執行：預設為專案根目錄

以實際啟動設定為準；`create_app` 可指定資料與資料庫目錄。升級／練習前先確認使用的是哪一份資料。不要用重裝環境代替備份。

## 開發驗證

在已安裝相依套件的環境執行：

```bash
python -m pytest -q
```

使用虛擬環境時，請將 `python` 換成上方該環境的 Python 路徑。單元／路由測試與真實瀏覽器驗證分開記錄；不能以 HTTP 測試宣稱互動截圖或完整瀏覽器驗證已完成。

## License

Internal use only.
