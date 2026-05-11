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

  // Whole-row expand / collapse — skip clicks on interactive elements
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

  searchInput?.addEventListener("input", recalculate);
  statusInput?.addEventListener("change", recalculate);
  recalculate();
}

bindMonitorTable();
