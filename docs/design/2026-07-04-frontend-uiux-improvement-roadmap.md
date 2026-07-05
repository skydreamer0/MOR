# Frontend UI/UX Improvement Roadmap（2026-07-04）

> **給執行代理（AI agent）：** 本文件是可分工的前端改善計劃。每個 Work Package（WP）自成一體，可由不同 agent 獨立執行。執行前必讀 `DESIGN.md` 與 `AGENTS.md` 的 Design Rules；完成一個 WP 後回到本文件勾選狀態並更新「已知衝突」備註。步驟使用 checkbox（`- [ ]`）語法追蹤。

**目標：** 在不改動預估邏輯、Excel schema、後端行為的前提下，提升 MOR 前端的操作安全性、輸入效率與一致性。

**架構原則：** 沿用現有 Flask + Jinja + vanilla JS + `static/css/mor.css` design token 體系。禁止引入前端框架與新第三方依賴（原生 `<dialog>`、IntersectionObserver 等瀏覽器內建 API 可用）。

**技術棧：** Jinja2 模板（`templates/`）、vanilla JS（`static/js/`）、單一 CSS（`static/css/mor.css`）、htmx（僅 Dashboard 指標區與 forecast row patch 已使用）。

---

## 執行規則（每個 WP 都適用）

1. Roadmap/spec 變更獨立成小 PR；實作 WP 可以依相容性批次累在同一個 implementation PR，不必一 WP 一 PR。
2. 實作批次內仍保持「一 WP 或一小子任務 = 一 commit」，方便 review、revert、cherry-pick。
3. 動工前先讀：`DESIGN.md`（token 與元件規則）、本 WP 列出的所有檔案。
4. 改 CSS 前先確認 selector 是否被 JS/htmx 引用（`static/js/*.js` 內 `querySelector`、模板內 `hx-*`）。
5. 驗證方式：
   - 後端測試不得變紅：macOS `python3 -m pytest -q`、Windows `D:\AI\python.exe -m pytest -q`。
   - 瀏覽器手動驗證：依 `docs/workflows/local-setup.md` 啟動 `app.py`，逐項執行 WP 內的「驗證」清單。
6. 完成後：更新本文件的 WP 狀態、若動到 token 或共用元件則同步更新 `DESIGN.md`。
7. Commit 訊息格式沿用現有慣例（如 `refactor(frontend): ...`、`feat(frontend): ...`）。

## 實作 PR 批次建議

- Batch A：WP3 + WP4，主題是輸入與表格操作效率。可累在同一 PR；若已存在 WP3 PR，可直接在該分支疊 WP4。
- Batch B：WP5 + WP6，主題是 polish、focus/aria、empty states、responsive cleanup。建議在 WP3/WP4 合併後再做。
- Speed mode：若 review 壓力可接受，WP3-WP6 可累在同一 implementation PR，但每個 WP 必須是獨立 commit，且 PR body 要列出每個 WP 的驗證結果。

## 子代理平行化規則

- 適合用子代理：WP4 的 template/table markup、monitor-table JS sorting、CSS sticky/sortable styling；WP5/WP6 的 accessibility audit、responsive CSS、empty-state template review。
- 不適合用子代理：同一檔案同一段 CSS 的競爭修改、需要即時手動瀏覽器操作的細節、尚未決定產品方向的開放問題。
- 主代理必須整合所有子代理結果，跑 focused tests + full `pytest`，並在 PR body 說明哪些驗證是自動、哪些因本地資料不足只能做靜態或模板檢查。

## WP 總覽與優先序

| WP | 主題 | 優先 | 狀態 | 主要檔案 |
| --- | --- | --- | --- | --- |
| WP1 | Header：導覽/動作分離 + 年月切換器 | P0 | ☑ 完成 | `_header.html`, `mor.css` |
| WP2 | 確認 dialog 元件 + 送出 loading 狀態 | P0 | ☑ 完成 | `_header.html`, `forecast.html`, `product_monitor.html`, 新 `static/js/ui-feedback.js`, `mor.css` |
| WP3 | 預估表格鍵盤操作（Enter/↑↓/Esc） | P1 | ☑ 完成 | `static/js/forecast-table.js` |
| WP4 | 表格排序 + 首欄 sticky | P1 | ☐ 未開始 | `static/js/monitor-table.js`, `mor.css`, `product_monitor.html` |
| WP5 | 字體堆疊 + focus/aria 細節 | P2 | ☐ 未開始 | `mor.css`, 各模板 icon 按鈕 |
| WP6 | 空狀態引導 + summary 收合改寫 + 響應式 | P2 | ☐ 未開始 | `forecast.html`, `mor.css` |

**平行執行衝突矩陣：**

- WP1 與 WP2 都會改 `templates/_header.html` 與 `mor.css` → 必須依序執行（先 WP1 後 WP2），或由同一 agent 承接。
- WP3 只改 `forecast-table.js` → 可與 WP4 累同一 PR，也可由不同子代理先調查。
- WP4 改 `monitor-table.js` + `product_monitor.html` + `mor.css`（表格區塊）→ 可和 WP3 累同一 PR；若和 WP5/WP6 平行，CSS 區塊需主代理最後整合。
- WP5、WP6 建議放最後，可累成一個 polish PR；若平行，請拆成 accessibility/template 與 CSS/responsive 兩條子代理工作。

---

## WP1 — Header：導覽/動作分離 + 年月切換器（P0）

**問題：** `_header.html` 中「同步資料」「上傳當月業績」兩個會改動資料的操作與導覽連結混排、樣式幾乎相同，容易誤觸。年月切換需要手動輸入兩個數字再按「套用」，但最常見的操作是切到上/下一個月。

**Files:**
- Modify: `templates/_header.html`
- Modify: `static/css/mor.css`（header 區塊，約 115–260 行附近）

- [x] **Step 1：把動作按鈕移出 `<nav>`，獨立成 `.header-actions` 區**

`templates/_header.html` 的 `<nav class="app-nav">` 只保留 7 個頁面連結；兩個 form 移到 nav 之後的新容器：

```html
<nav class="app-nav" aria-label="主要導覽">
  <a href="/" {% if active_page == "dashboard" %}aria-current="page"{% endif %}>業績總覽</a>
  <!-- ...其餘 6 個連結不變... -->
</nav>
<div class="header-actions">
  <form action="/sync" method="post" class="nav-action-form"
        data-confirm="確定要同步 Excel 資料到工作台？既有工作台資料將以 Excel 內容為準重建。"
        data-confirm-title="同步 Excel 資料">
    <button type="submit" class="nav-action-btn">同步資料</button>
  </form>
  <form action="/upload/current-month" method="post" enctype="multipart/form-data"
        class="nav-action-form"
        onsubmit="return !!this.querySelector('input[type=file]').files.length || (alert('請先選擇 SHPB 檔案') && false)">
    <label class="nav-action-btn nav-action-btn--file">
      上傳當月業績
      <input type="file" name="file" accept=".xlsx" style="display:none"
             onchange="this.closest('form').submit()">
    </label>
  </form>
</div>
```

註：`data-confirm` 屬性在 WP2 才會被 JS 接手；WP1 階段先保留原本的 `onsubmit="return confirm(...)"` 寫法，等 WP2 完成後移除（若 WP2 已先完成，直接用 `data-confirm`）。

- [x] **Step 2：CSS — 動作區加分隔線與次要按鈕樣式**

`mor.css` header 區塊新增：

```css
.header-actions {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  margin-left: auto;
  padding-left: var(--sp-4);
  border-left: 1px solid var(--line);
}

.header-actions .nav-action-btn {
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  background: var(--panel);
  color: var(--ink-secondary);
}

.header-actions .nav-action-btn:hover {
  border-color: var(--accent);
  color: var(--accent);
  background: var(--accent-subtle);
}
```

- [x] **Step 3：年月切換器 — 前後月箭頭 + 保留輸入框**

`_header.html` 的 period toolbar 改為：

```html
{% if show_period_toolbar %}
  {% set prev_year = year - 1 if month|int == 1 else year %}
  {% set prev_month = 12 if month|int == 1 else month|int - 1 %}
  {% set next_year = year + 1 if month|int == 12 else year %}
  {% set next_month = 1 if month|int == 12 else month|int + 1 %}
  {% set period_url = period_action | default(request.path, true) %}
  <form class="toolbar" method="get" action="{{ period_url }}">
    <a class="period-nav-btn" href="{{ period_url }}?year={{ prev_year }}&month={{ prev_month }}" aria-label="上一月">‹</a>
    <label>年度 <input name="year" type="number" min="2024" max="2030" value="{{ year }}"
      {% if active_page == "dashboard" %}hx-get="/dashboard/metrics" hx-target="#metrics-zone" hx-include="closest form" hx-swap="innerHTML" hx-trigger="change"{% endif %}></label>
    <label>月份 <input name="month" type="number" min="1" max="12" value="{{ month }}"
      {% if active_page == "dashboard" %}hx-get="/dashboard/metrics" hx-target="#metrics-zone" hx-include="closest form" hx-swap="innerHTML" hx-trigger="change"{% endif %}></label>
    <button type="submit">套用</button>
    <a class="period-nav-btn" href="{{ period_url }}?year={{ next_year }}&month={{ next_month }}" aria-label="下一月">›</a>
  </form>
{% endif %}
```

註：箭頭是一般連結（整頁導航），Dashboard 上不需要走 htmx——整頁 reload 時 metrics 一併更新，行為一致。

- [x] **Step 4：CSS — 箭頭按鈕**

```css
.period-nav-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: var(--control-h);
  height: var(--control-h);
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  background: var(--panel);
  color: var(--muted);
  text-decoration: none;
  font-size: var(--text-lg);
  line-height: 1;
  transition: color var(--duration) ease, border-color var(--duration) ease;
}

.period-nav-btn:hover {
  color: var(--accent);
  border-color: var(--accent);
}
```

- [x] **Step 5：驗證**

1. `python3 -m pytest -q`（或 Windows 對應指令）全綠。
2. 啟動 app，逐頁（/、/forecast、/monitor/products、/monthly-review、/settings）確認：導覽連結與動作按鈕視覺分離、`aria-current` 高亮正常。
3. 在 2026/01 按「‹」應跳到 2025/12；在 2026/12 按「›」應跳到 2027/01。
4. Dashboard 改月份輸入框仍走 htmx 局部更新（觀察 network 只打 `/dashboard/metrics`）。
5. 縮小視窗寬度至約 1100px，確認 header 換行時動作區不會蓋住導覽。

- [x] **Step 6：Commit**

```bash
git add templates/_header.html static/css/mor.css
git commit -m "feat(frontend): separate header actions from nav and add prev/next month switcher"
```

---

## WP2 — 確認 dialog 元件 + 送出 loading 狀態（P0）

**問題：** 「定稿」「結月」「同步」「刪除草稿」等不可逆操作目前用原生 `confirm()`，訊息短、樣式與系統不一致。同步/匯入是整頁 form POST，處理數秒期間沒有回饋、可重複送出。

**Files:**
- Create: `static/js/ui-feedback.js`
- Modify: `templates/_head_assets.html`（引入新 JS）
- Modify: `templates/_header.html`（同步 form）
- Modify: `templates/forecast.html`（刪除草稿 form；「定稿」按鈕在 `forecast-table.js` 內若有 confirm 也一併檢查）
- Modify: `templates/product_monitor.html`（結月 form）
- Modify: `static/css/mor.css`

- [x] **Step 1：建立共用 dialog markup**

在 `templates/_header.html` 檔尾（`</header>` 之後）加入全站共用 dialog：

```html
<dialog id="app-confirm" class="app-confirm">
  <form method="dialog">
    <h3 class="app-confirm__title" data-confirm-title>確認操作</h3>
    <p class="app-confirm__message" data-confirm-message></p>
    <div class="app-confirm__actions">
      <button value="cancel" class="btn-secondary">取消</button>
      <button value="ok" class="btn-danger" data-confirm-ok>確認</button>
    </div>
  </form>
</dialog>
```

- [x] **Step 2：建立 `static/js/ui-feedback.js`**

```js
/* ── 共用確認 dialog + form 送出 loading 狀態 ─────────────────
 * 用法：form 加上 data-confirm="訊息" [data-confirm-title="標題"]
 *       [data-confirm-ok="按鈕文字"] 即攔截 submit 改走 <dialog>。
 * 不支援 <dialog> 的環境自動 fallback 到原生 confirm()。
 */
(function () {
  "use strict";

  function appConfirm(opts) {
    const dlg = document.getElementById("app-confirm");
    if (!dlg || typeof dlg.showModal !== "function") {
      return Promise.resolve(window.confirm(opts.message));
    }
    dlg.querySelector("[data-confirm-title]").textContent = opts.title || "確認操作";
    dlg.querySelector("[data-confirm-message]").textContent = opts.message || "";
    dlg.querySelector("[data-confirm-ok]").textContent = opts.okLabel || "確認";
    return new Promise((resolve) => {
      dlg.addEventListener("close", () => resolve(dlg.returnValue === "ok"), { once: true });
      dlg.showModal();
    });
  }
  window.appConfirm = appConfirm;

  // data-confirm form 攔截
  document.addEventListener("submit", (e) => {
    const form = e.target;
    if (!(form instanceof HTMLFormElement) || !form.dataset.confirm) return;
    if (form.dataset.confirmed === "true") { form.dataset.confirmed = ""; return; }
    e.preventDefault();
    e.stopImmediatePropagation();
    appConfirm({
      title: form.dataset.confirmTitle,
      message: form.dataset.confirm,
      okLabel: form.dataset.confirmOk,
    }).then((ok) => {
      if (!ok) return;
      form.dataset.confirmed = "true";
      form.requestSubmit();
    });
  }, true);

  // 送出後 loading：加 is-loading、禁止重複送出
  document.addEventListener("submit", (e) => {
    if (e.defaultPrevented) return;
    const form = e.target;
    if (!(form instanceof HTMLFormElement) || form.dataset.noLoading === "true") return;
    const btn = form.querySelector('button[type="submit"], button:not([type])');
    if (!btn) return;
    btn.classList.add("is-loading");
    // 延後 disable，確保按鈕 value（若有）已隨表單送出
    setTimeout(() => { btn.disabled = true; }, 0);
  });
})();
```

- [x] **Step 3：`_head_assets.html` 引入**

在既有 script/style 引用後加：

```html
<script src="{{ url_for('static', filename='js/ui-feedback.js') }}" defer></script>
```

- [x] **Step 4：替換各處 `confirm()` 為 `data-confirm`**

- `_header.html` 同步 form：移除 `onsubmit`，改用 Step 1 之 `data-confirm`（WP1 已預埋屬性則只需移除 onsubmit）。
- `forecast.html:45` 刪除草稿 form：移除 `onsubmit`，加 `data-confirm="確定刪除此草稿？此動作無法復原。" data-confirm-title="刪除草稿" data-confirm-ok="刪除"`。
- `product_monitor.html` 結月 form：移除 `onsubmit`，加 `data-confirm="結月後無法再匯入或覆蓋本月實績，快照將被鎖定。" data-confirm-title="確認結月 {{ year }}/{{ '%02d'|format(month) }}" data-confirm-ok="結月"`。
- 檢查 `static/js/forecast-table.js` 內「定稿」（`#btn-finalize`）流程：若使用 `window.confirm`，改為 `await window.appConfirm({ title: "定稿本月預估", message: "定稿後本月預估將鎖定，無法再調整。", okLabel: "定稿" })`。

- [x] **Step 5：dialog 與 loading CSS**

```css
.app-confirm {
  min-width: 320px;
  max-width: 420px;
  border: 1px solid var(--line);
  border-radius: var(--radius-xl);
  padding: var(--sp-6);
  box-shadow: var(--shadow-lg);
}

.app-confirm::backdrop {
  background: rgba(15, 23, 42, 0.35);
  backdrop-filter: blur(2px);
}

.app-confirm__title { margin: 0 0 var(--sp-2); font-size: var(--text-lg); }
.app-confirm__message { margin: 0 0 var(--sp-5); color: var(--muted); }
.app-confirm__actions { display: flex; justify-content: flex-end; gap: var(--sp-2); }

button.is-loading {
  position: relative;
  color: transparent !important;
  pointer-events: none;
}

button.is-loading::after {
  content: "";
  position: absolute;
  inset: 0;
  margin: auto;
  width: 14px;
  height: 14px;
  border: 2px solid var(--line);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: mor-spin 0.6s linear infinite;
}

@keyframes mor-spin { to { transform: rotate(360deg); } }
```

- [x] **Step 6：驗證**

1. `python3 -m pytest -q` 全綠。
2. 同步資料：出現自訂 dialog → 取消不送出、確認送出且按鈕轉 loading、無法連點。
3. 結月、刪除草稿、定稿逐一驗證 dialog 文案與後果說明。
4. htmx 的 row patch（人工調整輸入）不受影響（`hx-patch` 不觸發 loading 全域邏輯，因其非 form submit）。
5. 用 Safari 與 Chrome 各驗一次（`<dialog>` 支援度）。

- [x] **Step 7：Commit**

```bash
git add static/js/ui-feedback.js templates static/css/mor.css
git commit -m "feat(frontend): shared confirm dialog and submit loading states"
```

---

## WP3 — 預估表格鍵盤操作（P1）

**問題：** 預估調整是逐列輸入密集操作，但 `[data-manual]` 數量欄位間無鍵盤移動，只能滑鼠逐格點。

**Files:**
- Modify: `static/js/forecast-table.js`

**前置理解（執行 agent 必讀）：**
- 每列 `<tr data-row>` 由 `templates/_forecast_row.html` 產生；數量欄位是 `input.qty[data-manual]`，change 時經 htmx `hx-patch` 以 `outerHTML` 置換整列。
- 置換後的列需要重綁 sparkline 等（檢查現有 `htmx:afterSwap` 或等效處理；若透過事件委派則不需重綁）。
- 篩選隱藏的列以 `style.display === "none"`（確認 `recalculate()` 內實際做法後對齊）。

- [x] **Step 1：新增鍵盤導航函式**

在 `forecast-table.js` 中加入，並在初始化流程（現有 `bindForecastTable()` 或等效入口）呼叫：

```js
function visibleDataRows() {
  return Array.from(document.querySelectorAll("[data-row]"))
    .filter((r) => r.style.display !== "none" && !r.hidden);
}

function bindKeyboardNavigation() {
  document.addEventListener("keydown", (e) => {
    const input = e.target instanceof Element ? e.target.closest("[data-manual]") : null;
    if (!input) return;

    if (e.key === "Escape") {
      const restore = input.closest("[data-row]")?.querySelector("[data-restore]");
      if (restore && !restore.hidden) restore.click();
      return;
    }
    if (e.key !== "Enter" && e.key !== "ArrowDown" && e.key !== "ArrowUp") return;

    e.preventDefault(); // 阻止 ArrowUp/Down 改變 number input 數值
    const rows = visibleDataRows();
    const idx = rows.indexOf(input.closest("[data-row]"));
    if (idx === -1) return;
    const nextIdx = e.key === "ArrowUp" ? idx - 1 : idx + 1;
    const target = rows[nextIdx]?.querySelector("[data-manual]");
    if (target) {
      target.focus();
      target.select();
    }
  });
}
```

使用 document 層級委派：htmx 以 `outerHTML` 置換列之後不需重綁。

- [x] **Step 2：驗證**

1. `/forecast` 頁：在任一數量欄按 Enter → 焦點移到下一可見列的數量欄且全選；↑/↓ 對應上下移動；數值不被方向鍵改動。
2. Enter 移動後，原列因 change 觸發 `hx-patch` 置換 → 確認置換不奪走新焦點、最後預估/差異即時更新。
3. 套用「只看異常」或客戶篩選後，鍵盤移動只在可見列間跳。
4. 有人工值的列按 Esc → 觸發「還原」按鈕。
5. `python3 -m pytest -q` 全綠（此 WP 不動後端，屬回歸保險）。

- [x] **Step 3：Commit**

```bash
git add static/js/forecast-table.js
git commit -m "feat(frontend): spreadsheet-style keyboard navigation for forecast quantity inputs"
```

---

## WP4 — 表格排序 + 首欄 sticky（P1）

**問題：** 跳單監控與 Dashboard 高風險表無法點表頭排序（排「差異」「金額影響」是自然需求）；寬表格橫向捲動時客戶/品項欄會捲出視野。

**Files:**
- Modify: `static/js/monitor-table.js`
- Modify: `templates/product_monitor.html`（表頭加 `data-sort` 屬性）
- Modify: `static/css/mor.css`

- [ ] **Step 1：monitor 表頭標記可排序欄**

`product_monitor.html` 跳單明細表 `<thead>` 的數值欄（去年同期、預估月底、差異、金額影響等）與文字欄（客戶）加上：

```html
<th class="num sortable" data-sort="number" role="button" tabindex="0" aria-sort="none">差異</th>
<th class="sortable" data-sort="text" role="button" tabindex="0" aria-sort="none">客戶</th>
```

（依實際欄位逐一標記；不可排序的欄不加屬性。）

- [ ] **Step 2：`monitor-table.js` 加排序邏輯**

```js
function bindSorting(table) {
  const tbody = table.querySelector("tbody");
  table.querySelectorAll("th[data-sort]").forEach((th, _, allTh) => {
    const activate = () => {
      const dir = th.getAttribute("aria-sort") === "ascending" ? "descending" : "ascending";
      allTh.forEach((h) => h.setAttribute("aria-sort", "none"));
      th.setAttribute("aria-sort", dir);
      const colIdx = Array.from(th.parentNode.children).indexOf(th);
      const numeric = th.dataset.sort === "number";
      const rows = Array.from(tbody.querySelectorAll("tr"));
      rows.sort((a, b) => {
        const av = a.children[colIdx]?.textContent.trim() ?? "";
        const bv = b.children[colIdx]?.textContent.trim() ?? "";
        if (numeric) {
          const an = parseFloat(av.replace(/[,+%]/g, "")) || 0;
          const bn = parseFloat(bv.replace(/[,+%]/g, "")) || 0;
          return dir === "ascending" ? an - bn : bn - an;
        }
        return dir === "ascending" ? av.localeCompare(bv, "zh-Hant") : bv.localeCompare(av, "zh-Hant");
      });
      rows.forEach((r) => tbody.appendChild(r));
    };
    th.addEventListener("click", activate);
    th.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); activate(); }
    });
  });
}
```

在現有 monitor 表初始化處呼叫 `bindSorting(document.querySelector(".monitor-table 或實際 class"))`（以檔案內實際 selector 為準）。排序需與現有搜尋/篩選共存：排序只重排 DOM 順序，不影響 display 隱藏邏輯。

- [ ] **Step 3：排序視覺 + 首欄 sticky CSS**

```css
th.sortable { cursor: pointer; user-select: none; }
th.sortable:hover { color: var(--accent); }
th.sortable[aria-sort="ascending"]::after  { content: " ↑"; color: var(--accent); }
th.sortable[aria-sort="descending"]::after { content: " ↓"; color: var(--accent); }

/* 寬表格首欄 sticky（預估表 + 監控表） */
.forecast-table th:first-child,
.forecast-table td:first-child {
  position: sticky;
  left: 0;
  z-index: 2;
  background: var(--panel);
}

.forecast-table thead th:first-child { z-index: 3; }
```

注意：列 hover 底色（`--row-hover`）與狀態 accent bar 若因 sticky 背景被遮蓋，需將對應背景規則同步套到 `td:first-child`（以實際樣式為準，hover 時 `background: var(--row-hover)`）。監控表若同樣會橫向捲動，比照辦理。

- [ ] **Step 4：驗證**

1. 跳單明細表點「差異」表頭 → 依數值升冪，再點降冪，箭頭指示正確；千分位與 `+/-` 符號不影響排序。
2. 排序後套用搜尋/狀態篩選 → 隱藏邏輯正常、計數正確。
3. `/forecast` 橫向捲動 → 客戶欄固定在左側、hover 底色一致、與 sticky 表頭交會處無破版。
4. 鍵盤 Tab 到表頭按 Enter 可排序（無障礙）。
5. `python3 -m pytest -q` 全綠。

- [ ] **Step 5：Commit**

```bash
git add static/js/monitor-table.js templates/product_monitor.html static/css/mor.css
git commit -m "feat(frontend): sortable monitor columns and sticky first column for wide tables"
```

---

## WP5 — 字體堆疊 + focus/aria 細節（P2）

**問題：** font stack 以 `"Microsoft JhengHei"` 開頭，macOS 落到 Segoe UI/Arial，中文渲染不受控。focus ring 用天藍（`--focus: #38bdf8`）與品牌 teal 不同色系。icon 按鈕以文字「X」「✕」呈現、缺 aria-label。

**Files:**
- Modify: `static/css/mor.css`
- Modify: `templates/forecast.html`（`#rd-close`、刪除草稿 `icon-btn`）
- Modify: `DESIGN.md`（字體與 focus token 說明同步更新）

- [ ] **Step 1：字體堆疊**

`mor.css` body 的 `font-family` 改為：

```css
font-family: "Microsoft JhengHei", "PingFang TC", "Noto Sans TC", "Segoe UI", system-ui, Arial, sans-serif;
```

（Windows 為主要部署平台故 JhengHei 保持第一；PingFang TC 讓 macOS 開發/驗證時中文正常。）

- [ ] **Step 2：focus ring 統一為品牌色系**

```css
--focus:      #0d9488;
--focus-ring: rgba(13, 148, 136, 0.25);
```

全域搜尋 `--focus` 使用處確認視覺（input focus、按鈕 focus-visible），對比不足時可保留天藍——由執行 agent 在瀏覽器實際比對後二選一，並把決定寫回 `DESIGN.md`。

- [ ] **Step 3：icon 按鈕 aria-label**

- `forecast.html` 刪除草稿按鈕：`<button type="submit" class="icon-btn" title="刪除草稿" aria-label="刪除草稿">✕</button>`（同時把「X」統一為「✕」）。
- `#rd-close`：加 `aria-label="關閉詳細資料"`。
- 全域 grep `icon-btn` 確認每個都有 `aria-label` 或可見文字。

- [ ] **Step 4：驗證與 Commit**

1. macOS + Windows（或瀏覽器 devtools 模擬字體停用）確認中文字體 fallback。
2. Tab 走查 forecast 工具列與表格輸入框，focus ring 一致清晰。
3. `python3 -m pytest -q` 全綠。

```bash
git add static/css/mor.css templates DESIGN.md
git commit -m "refactor(frontend): font stack, unified focus ring, icon button aria labels"
```

---

## WP6 — 空狀態引導 + summary 收合改寫 + 響應式（P2）

**問題：** 空狀態只有一句話沒有下一步；forecast summary 收合依賴 `wheel` 事件（鍵盤捲動/觸控慣性不觸發）；768px 以外中間寬度沒有收斂策略。

**Files:**
- Modify: `templates/forecast.html`
- Modify: `static/css/mor.css`

- [ ] **Step 1：空狀態加行動引導**

`forecast.html` 的空狀態改為：

```html
<section class="empty-state">
  <p>沒有可調整的預估資料。</p>
  <p class="muted">請先同步 Excel 資料，或切換到有資料的月份。</p>
  <form action="/sync" method="post" data-confirm="確定要同步 Excel 資料到工作台？" data-confirm-title="同步 Excel 資料">
    <button type="submit" class="btn-secondary">同步資料</button>
  </form>
</section>
```

（`data-confirm` 依賴 WP2；若 WP2 未完成則暫用 `onsubmit="return confirm(...)"`。）

- [ ] **Step 2：summary 收合改為 scroll 位置判斷**

替換 `forecast.html` 檔尾的 wheel/scroll IIFE：

```js
// 捲動 table-wrap 收合 summary：以 scrollTop 門檻判斷，鍵盤/觸控捲動皆適用
(function () {
  const summary   = document.querySelector('.summary');
  const tableWrap = document.querySelector('.table-wrap');
  if (!summary || !tableWrap) return;
  tableWrap.addEventListener('scroll', () => {
    summary.classList.toggle('summary--collapsed', tableWrap.scrollTop > 24);
  }, { passive: true });
})();
```

註：原 wheel 寫法是為了「列數不足、無捲動空間」時也能收合，但該情境下本來就不需要收合（內容已全部可見），可安全移除。

- [ ] **Step 3：中間寬度響應式**

`mor.css` 新增 1100px 斷點，讓導覽可橫向捲動而非擠壓換行：

```css
@media (max-width: 1100px) {
  .app-nav {
    overflow-x: auto;
    flex-wrap: nowrap;
    scrollbar-width: none;
  }
  .app-nav::-webkit-scrollbar { display: none; }
}
```

- [ ] **Step 4：驗證與 Commit**

1. 切到沒有資料的月份 → 空狀態顯示引導與同步按鈕，按鈕可用。
2. `/forecast` 用滑鼠滾輪、鍵盤 PgDn、觸控板分別捲動 → summary 收合/展開一致；回到頂部展開。
3. 視窗寬度 900–1100px → 導覽列單行橫向捲動、不擠壓動作按鈕。
4. `python3 -m pytest -q` 全綠。

```bash
git add templates/forecast.html static/css/mor.css
git commit -m "refactor(frontend): actionable empty state, scroll-based summary collapse, mid-width nav"
```

---

## 完成定義（整體）

- 6 個 WP 全數勾選，或被明確標記為「不做」並附原因。
- `pytest` 全綠、每個 WP 的瀏覽器驗證清單逐項通過。
- `DESIGN.md` 與本文件狀態表同步更新。
- 未引入任何新第三方依賴、未改動後端行為與 Excel schema。
