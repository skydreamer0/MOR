const MonitorTable = (() => {
  "use strict";

  function sortToken(row, key, type, column) {
    const dataKey = `sort${key.charAt(0).toUpperCase()}${key.slice(1)}`;
    const raw = row.dataset?.[dataKey] ?? row.cells?.[column]?.textContent ?? "";
    const text = String(raw).trim();
    if (type === "number") {
      const value = Number(text.replace(/,/g, ""));
      return Number.isFinite(value) ? value : null;
    }
    if (type === "date") {
      const value = Date.parse(text);
      return Number.isNaN(value) ? null : value;
    }
    return text.toLocaleLowerCase("zh-Hant");
  }

  function compareValues(a, b, direction) {
    if (a === null && b === null) return 0;
    if (a === null) return 1;
    if (b === null) return -1;
    if (typeof a === "number" && typeof b === "number") {
      return direction === "asc" ? a - b : b - a;
    }
    const result = String(a).localeCompare(String(b), "zh-Hant", { numeric: true });
    return direction === "asc" ? result : -result;
  }

  function sortRows(tbody, rows, sort) {
    const pairs = new Map(rows.map((row) => {
      const detail = row.nextElementSibling;
      return [row, detail?.hasAttribute("data-monitor-detail") ? detail : null];
    }));

    rows.sort((a, b) => {
      if (a.hidden !== b.hidden) return a.hidden ? 1 : -1;
      const result = compareValues(
        sortToken(a, sort.key || "", sort.type || "text", sort.column),
        sortToken(b, sort.key || "", sort.type || "text", sort.column),
        sort.direction || "asc"
      );
      return result || ((a.dataset?.initialIndex || 0) - (b.dataset?.initialIndex || 0));
    });

    rows.forEach((row) => {
      tbody.appendChild(row);
      const detail = pairs.get(row);
      if (detail) {
        tbody.appendChild(detail);
      }
    });
  }

  function applySortState(headers, activeHeader, direction) {
    headers.forEach((header) => {
      const active = header === activeHeader;
      header.setAttribute("aria-sort", active ? (direction === "asc" ? "ascending" : "descending") : "none");
      header.querySelector("[data-monitor-sort-indicator]")?.setAttribute("aria-hidden", "true");
    });
  }

  function bindSorting(rows) {
    const headers = Array.from(document.querySelectorAll("[data-monitor-sort]"));
    const tbody = rows[0]?.parentElement;
    if (!headers.length || !tbody) return;

    rows.forEach((row, index) => {
      row.dataset.initialIndex = String(index);
    });

    headers.forEach((header) => {
      const trigger = header.querySelector("button") || header;
      const runSort = () => {
        const current = header.dataset.sortDirection || "";
        const direction = current === "asc" ? "desc" : "asc";
        headers.forEach((h) => { h.dataset.sortDirection = ""; });
        header.dataset.sortDirection = direction;
        applySortState(headers, header, direction);
        sortRows(tbody, rows, {
          key: header.dataset.monitorSort,
          column: Number(header.dataset.monitorSortColumn || 0),
          type: header.dataset.monitorSortType || "text",
          direction,
        });
      };
      trigger.addEventListener("click", runSort);
    });
  }

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
  bindSorting(rows);
  recalculate();
  }

  return { bindMonitorTable, sortRows };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = MonitorTable;
} else {
  MonitorTable.bindMonitorTable();
}
