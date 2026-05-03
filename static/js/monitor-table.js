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
      if (shouldShow) visible += 1;
    });

    if (visibleCount) visibleCount.textContent = new Intl.NumberFormat("zh-TW").format(visible);
  }

  searchInput?.addEventListener("input", recalculate);
  statusInput?.addEventListener("change", recalculate);
  recalculate();
}

bindMonitorTable();
