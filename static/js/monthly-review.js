(function () {
  var toggle = document.getElementById("review-only-anomalies");
  var filter = document.getElementById("review-detail-filter");
  var search = document.getElementById("review-detail-search");
  var count = document.getElementById("review-detail-count");
  var table = document.getElementById("review-detail-table");

  if (!table) return;

  function matchesFilter(row, selected) {
    if (selected === "anomaly") return row.getAttribute("data-anomaly") === "1";
    if (selected === "yoy") return row.getAttribute("data-yoy-risk") === "1";
    if (selected === "budget") return row.getAttribute("data-budget-risk") === "1";
    if (selected === "forecast") return row.getAttribute("data-forecast-risk") === "1";
    return true;
  }

  function applyFilters() {
    var selected = filter ? filter.value : "all";
    var onlyAnomalies = toggle && toggle.checked;
    var query = search ? search.value.trim().toLowerCase() : "";
    var visible = 0;

    table.querySelectorAll("tbody tr").forEach(function (row) {
      var rowText = row.getAttribute("data-search") || "";
      var show = matchesFilter(row, selected);
      if (onlyAnomalies) show = show && row.getAttribute("data-anomaly") === "1";
      if (query) show = show && rowText.indexOf(query) !== -1;
      row.hidden = !show;
      if (show) visible += 1;
    });

    if (count) count.textContent = visible + " 筆";
  }

  if (toggle) toggle.addEventListener("change", applyFilters);
  if (filter) filter.addEventListener("change", applyFilters);
  if (search) search.addEventListener("input", applyFilters);
  applyFilters();

  var printState = [];

  window.addEventListener("beforeprint", function () {
    printState = [];
    document.querySelectorAll(".review-disclosure").forEach(function (section) {
      printState.push([section, section.open]);
      section.open = true;
    });
  });

  window.addEventListener("afterprint", function () {
    printState.forEach(function (entry) {
      entry[0].open = entry[1];
    });
    printState = [];
  });
})();
