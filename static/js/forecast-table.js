const formatter = new Intl.NumberFormat("zh-TW", { maximumFractionDigits: 0 });

function readRowState(row) {
  const manualInput = row.querySelector("[data-manual]");
  const excludedInput = row.querySelector("[data-exclude]");
  return {
    row,
    rowId: row.dataset.rowId,
    status: row.dataset.status,
    searchText: (row.dataset.search || "").toLowerCase(),
    price: Number(row.dataset.price || 0),
    autoQuantity: Number(row.dataset.autoQty || 0),
    manualValue: manualInput.value,
    excluded: excludedInput.checked,
  };
}

function effectiveQuantity(state) {
  return state.manualValue === "" ? state.autoQuantity : Number(state.manualValue);
}

function calculateAmount(state) {
  return state.excluded ? 0 : effectiveQuantity(state) * state.price;
}

function isEdited(state) {
  return state.manualValue !== "";
}

function hasInvalidManualQuantity(state) {
  return state.manualValue !== "" && (Number.isNaN(Number(state.manualValue)) || Number(state.manualValue) < 0);
}

function matchesFilters(state, searchValue, statusValue) {
  const matchesSearch = searchValue === "" || state.searchText.includes(searchValue);
  let matchesStatus = true;

  if (statusValue === "auto" || statusValue === "not_due") {
    matchesStatus = state.status === statusValue;
  } else if (statusValue === "edited") {
    matchesStatus = isEdited(state);
  } else if (statusValue === "excluded") {
    matchesStatus = state.excluded;
  }

  return matchesSearch && matchesStatus;
}

function renderRow(state, amount, visible) {
  const invalid = hasInvalidManualQuantity(state);
  state.row.classList.toggle("excluded", state.excluded);
  state.row.classList.toggle("edited", isEdited(state));
  state.row.classList.toggle("invalid", invalid);
  state.row.hidden = !visible;
  state.row.querySelector("[data-manual]").setAttribute("aria-invalid", invalid ? "true" : "false");
  state.row.querySelector("[data-amount]").textContent = formatter.format(amount);
}

function recalculate() {
  const searchInput = document.querySelector("[data-filter-search]");
  const statusInput = document.querySelector("[data-filter-status]");
  const searchValue = (searchInput?.value || "").trim().toLowerCase();
  const statusValue = statusInput?.value || "all";
  let total = 0;
  let visibleCount = 0;
  let editedCount = 0;
  let excludedCount = 0;

  document.querySelectorAll("[data-row]").forEach((row) => {
    const state = readRowState(row);
    const amount = calculateAmount(state);
    const visible = matchesFilters(state, searchValue, statusValue);

    total += amount;
    if (visible) visibleCount += 1;
    if (isEdited(state)) editedCount += 1;
    if (state.excluded) excludedCount += 1;
    renderRow(state, amount, visible);
  });

  document.getElementById("grand-total").textContent = formatter.format(total);
  document.getElementById("top-total").textContent = formatter.format(total);
  document.querySelector("[data-visible-count]").textContent = formatter.format(visibleCount);
  document.querySelector("[data-edited-count]").textContent = formatter.format(editedCount);
  document.querySelector("[data-excluded-count]").textContent = formatter.format(excludedCount);
}

function validateBeforeSubmit(event) {
  const validationMessage = document.querySelector("[data-validation-message]");
  let firstInvalidInput = null;

  document.querySelectorAll("[data-row]").forEach((row) => {
    const state = readRowState(row);
    const invalid = hasInvalidManualQuantity(state);
    row.classList.toggle("invalid", invalid);
    row.querySelector("[data-manual]").setAttribute("aria-invalid", invalid ? "true" : "false");
    if (invalid && firstInvalidInput === null) {
      firstInvalidInput = row.querySelector("[data-manual]");
      row.hidden = false;
    }
  });

  if (firstInvalidInput) {
    event.preventDefault();
    validationMessage.hidden = false;
    firstInvalidInput.focus();
    return false;
  }

  validationMessage.hidden = true;
  return true;
}

function bindForecastTable() {
  document.querySelectorAll("[data-manual], [data-exclude], [data-filter-search], [data-filter-status]").forEach((input) => {
    input.addEventListener("input", recalculate);
    input.addEventListener("change", recalculate);
  });
  document.getElementById("forecast-form").addEventListener("submit", validateBeforeSubmit);
  recalculate();
}

bindForecastTable();
