function bindItemSettingsSearch() {
  const searchInput = document.querySelector("[data-item-search]");
  const visibleCount = document.querySelector("[data-item-visible]");
  const rows = Array.from(document.querySelectorAll("[data-item-row]"));

  function recalculate() {
    const searchValue = (searchInput?.value || "").trim().toLowerCase();
    let visible = 0;

    rows.forEach((row) => {
      const matchesSearch = searchValue === "" || (row.dataset.search || "").toLowerCase().includes(searchValue);
      row.hidden = !matchesSearch;
      if (matchesSearch) visible += 1;
    });

    if (visibleCount) visibleCount.textContent = new Intl.NumberFormat("zh-TW").format(visible);
  }

  searchInput?.addEventListener("input", recalculate);
  recalculate();
}

bindItemSettingsSearch();
