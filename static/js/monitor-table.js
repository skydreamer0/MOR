function bindMonitorTable() {
  const searchInput  = document.querySelector("[data-monitor-search]");
  const statusInput  = document.querySelector("[data-monitor-status]");
  const exportBtn    = document.querySelector("[data-monitor-export]");
  const visibleCount = document.querySelector("[data-monitor-visible]");
  const rows         = Array.from(document.querySelectorAll("[data-monitor-row]"));

  // ── Filter ──────────────────────────────────────────────────────────────
  function matchesSearch(row, keywords) {
    if (keywords.length === 0) return true;
    const haystack = (row.dataset.search || "").toLowerCase();
    return keywords.every(kw => haystack.includes(kw));
  }

  function matchesStatus(row, value) {
    if (value === "all")              return true;
    if (value === "cycle_delayed")    return row.dataset.cycleStatus === "delayed";
    if (value === "cycle_approaching")return row.dataset.cycleStatus === "approaching";
    if (value === "gap_rising")       return row.dataset.gapTrend   === "rising";
    if (value === "gap_falling")      return row.dataset.gapTrend   === "falling";
    return row.dataset.status === value;
  }

  function recalculate() {
    const raw    = (searchInput?.value || "").trim().toLowerCase();
    const keywords = raw.split(/\s+/).filter(Boolean);
    const statusValue = statusInput?.value || "all";
    let visible = 0;

    rows.forEach((row) => {
      const shouldShow = matchesSearch(row, keywords) && matchesStatus(row, statusValue);
      row.hidden = !shouldShow;

      // Collapse detail row when main row is filtered out
      const detail = row.nextElementSibling;
      if (detail?.hasAttribute("data-monitor-detail") && !shouldShow) {
        detail.hidden = true;
        row.setAttribute("aria-expanded", "false");
      }

      if (shouldShow) visible += 1;
    });

    if (visibleCount) visibleCount.textContent = new Intl.NumberFormat("zh-TW").format(visible);
  }

  // ── Row expand / collapse ────────────────────────────────────────────────
  document.addEventListener("click", (e) => {
    if (e.target.closest("button, a, input, select, label")) return;
    const mainRow = e.target.closest("[data-monitor-row]");
    if (!mainRow) return;
    const detail = mainRow.nextElementSibling;
    if (!detail?.hasAttribute("data-monitor-detail")) return;
    const expanded = mainRow.getAttribute("aria-expanded") === "true";
    mainRow.setAttribute("aria-expanded", String(!expanded));
    detail.hidden = expanded;
  });

  // ── CSV Export ───────────────────────────────────────────────────────────
  function exportCsv() {
    const HEADERS = [
      "客戶", "品項", "整體狀態",
      "最近出貨日", "距出貨(工作天)", "週期狀態",
      "本月目前", "推估月底", "最終預估",
      "去年成長率", "預算達成率",
      "間隔趨勢",
    ];

    const visibleRows = rows.filter(r => !r.hidden);
    const body = visibleRows.map(r => [
      r.dataset.csvCustomer     || "",
      r.dataset.csvProduct      || "",
      r.dataset.csvStatus       || "",
      r.dataset.csvDate         || "",
      r.dataset.csvCycleDays    || "",
      r.dataset.csvCycleStatus  || "",
      r.dataset.csvCurrent      || "",
      r.dataset.csvEom          || "",
      r.dataset.csvForecast     || "",
      r.dataset.csvYoy          || "",
      r.dataset.csvBudget       || "",
      r.dataset.csvGapTrend     || "",
    ]);

    const escape = v => `"${String(v).replace(/"/g, '""')}"`;
    const csv = [HEADERS, ...body]
      .map(row => row.map(escape).join(","))
      .join("\r\n");

    // UTF-8 BOM so Excel opens Chinese correctly
    const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8;" });
    const url  = URL.createObjectURL(blob);
    const a    = Object.assign(document.createElement("a"), {
      href: url,
      download: `monitor_${new Date().toISOString().slice(0, 10)}.csv`,
    });
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  // ── Event bindings ───────────────────────────────────────────────────────
  searchInput?.addEventListener("input", recalculate);
  statusInput?.addEventListener("change", recalculate);
  exportBtn?.addEventListener("click", exportCsv);
  recalculate();
}

bindMonitorTable();
