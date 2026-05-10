function bindMonitorTable() {
  const searchInput = document.querySelector("[data-monitor-search]");
  const statusInput = document.querySelector("[data-monitor-status]");
  const visibleCount = document.querySelector("[data-monitor-visible]");
  const rows = Array.from(document.querySelectorAll("[data-monitor-row]"));

  function recalculate() {
    const searchValue = (searchInput?.value || "").trim().toLowerCase();
    const statusValue = statusInput?.value || "all";
    let visible = 0;

    rows.forEach((row) => {
      const matchesSearch = searchValue === "" || (row.dataset.search || "").toLowerCase().includes(searchValue);
      const matchesStatus = statusValue === "all" || row.dataset.status === statusValue;
      const shouldShow = matchesSearch && matchesStatus;
      row.hidden = !shouldShow;

      // Keep detail row in sync: hide it whenever its main row is filtered out
      const detail = row.nextElementSibling;
      if (detail?.hasAttribute("data-monitor-detail") && !shouldShow) {
        detail.hidden = true;
        const btn = row.querySelector("[data-monitor-expand]");
        if (btn) btn.setAttribute("aria-expanded", "false");
      }

      if (shouldShow) visible += 1;
    });

    if (visibleCount) visibleCount.textContent = new Intl.NumberFormat("zh-TW").format(visible);
  }

  // Expand / collapse detail rows
  document.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-monitor-expand]");
    if (!btn) return;
    const mainRow = btn.closest("[data-monitor-row]");
    const detail = mainRow?.nextElementSibling;
    if (!detail?.hasAttribute("data-monitor-detail")) return;
    const expanded = btn.getAttribute("aria-expanded") === "true";
    btn.setAttribute("aria-expanded", String(!expanded));
    btn.textContent = expanded ? "▶" : "▼";
    detail.hidden = expanded;
  });

  searchInput?.addEventListener("input", recalculate);
  statusInput?.addEventListener("change", recalculate);
  recalculate();
}

bindMonitorTable();
