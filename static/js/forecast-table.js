const formatter = new Intl.NumberFormat("zh-TW", { maximumFractionDigits: 0 });
const precisionFormatter = new Intl.NumberFormat("zh-TW", { maximumFractionDigits: 2 });

/* ── Sparkline Renderer ─────────────────────────────────────────── */

/**
 * Draw a minimal sparkline on a <canvas> element.
 * - No axes, only the trend line.
 * - Last data point gets an emphasized dot.
 * - Line colour shifts green→red based on trend direction.
 */
function drawSparkline(canvas, data) {
  if (!canvas || !data || data.length === 0) return;

  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth || 80;
  const h = canvas.clientHeight || 24;
  canvas.width = w * dpr;
  canvas.height = h * dpr;

  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);

  const pad = 3;
  const plotW = w - pad * 2;
  const plotH = h - pad * 2;

  const max = Math.max(...data, 1); // avoid division by 0
  const min = Math.min(...data, 0);
  const range = max - min || 1;

  const points = data.map((v, i) => ({
    x: pad + (i / Math.max(data.length - 1, 1)) * plotW,
    y: pad + plotH - ((v - min) / range) * plotH,
  }));

  // Determine trend colour: compare last vs first non-zero
  const first = data.find((v) => v > 0) ?? 0;
  const last = data[data.length - 1];
  const trendUp = last >= first;
  const lineColor = trendUp
    ? "rgba(4, 120, 87, 0.7)"   // success-text
    : "rgba(220, 38, 38, 0.7)"; // danger
  const dotColor = trendUp
    ? "rgb(4, 120, 87)"
    : "rgb(220, 38, 38)";
  const fillColor = trendUp
    ? "rgba(4, 120, 87, 0.06)"
    : "rgba(220, 38, 38, 0.06)";

  // Area fill
  ctx.beginPath();
  ctx.moveTo(points[0].x, h - pad);
  points.forEach((p) => ctx.lineTo(p.x, p.y));
  ctx.lineTo(points[points.length - 1].x, h - pad);
  ctx.closePath();
  ctx.fillStyle = fillColor;
  ctx.fill();

  // Line
  ctx.beginPath();
  points.forEach((p, i) => (i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y)));
  ctx.strokeStyle = lineColor;
  ctx.lineWidth = 1.5;
  ctx.lineJoin = "round";
  ctx.lineCap = "round";
  ctx.stroke();

  // Last-point dot (emphasized)
  const lastPt = points[points.length - 1];
  ctx.beginPath();
  ctx.arc(lastPt.x, lastPt.y, 2.5, 0, Math.PI * 2);
  ctx.fillStyle = dotColor;
  ctx.fill();
}

/**
 * Render all sparklines on the page.
 * Called once on load.
 */
function renderAllSparklines() {
  document.querySelectorAll("[data-row]").forEach((row) => {
    const canvas = row.querySelector("[data-sparkline]");
    if (!canvas) return;
    try {
      const trend = JSON.parse(row.dataset.trend || "[]");
      drawSparkline(canvas, trend);
    } catch {
      // Silently skip if data is malformed
    }
  });
}


/* ── Core Table Logic ───────────────────────────────────────────── */

function readRowState(row) {
  const manualInput = row.querySelector("[data-manual]");
  const reasonInput = row.querySelector("[data-reason]");
  return {
    row,
    rowId: row.dataset.rowId,
    status: row.dataset.status,
    searchText: (row.dataset.search || "").toLowerCase(),
    price: Number(row.dataset.price || 0),
    systemForecast: Number(row.dataset.systemQty || 0),
    actualQuantity: Number(row.dataset.actualQty || 0),
    manualValue: manualInput.value,
    reason: reasonInput.value,
    excluded: row.dataset.excluded === "true",
  };
}

function finalForecastQuantity(state) {
  return state.manualValue === "" ? state.systemForecast : Number(state.manualValue);
}

function calculateAmount(state) {
  return state.excluded ? 0 : finalForecastQuantity(state) * state.price;
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
  }

  return matchesSearch && matchesStatus;
}

function renderRow(state, amount, visible) {
  const invalid = hasInvalidManualQuantity(state);
  state.row.classList.toggle("edited", isEdited(state));
  state.row.classList.toggle("invalid", invalid);
  state.row.hidden = !visible;

  const manualInput = state.row.querySelector("[data-manual]");
  manualInput.setAttribute("aria-invalid", invalid ? "true" : "false");

  const finalQty = finalForecastQuantity(state);
  const diff = finalQty - state.actualQuantity;

  // Budget & Rate
  const budget = Number(state.row.dataset.budget || 0);
  const rate = budget > 0 ? (finalQty / budget) * 100 : 0;
  const rateEl = state.row.querySelector("[data-rate-display] .rate");
  if (rateEl) {
    rateEl.textContent = rate.toFixed(1) + "%";
    rateEl.classList.toggle("low", rate < 80);
    rateEl.classList.toggle("high", rate >= 100);
  }

  state.row.querySelector("[data-final-forecast]").textContent = precisionFormatter.format(finalQty);
  state.row.querySelector("[data-diff]").textContent = precisionFormatter.format(diff);
  state.row.querySelector("[data-amount]").textContent = formatter.format(amount);
}

function recalculate() {
  const searchInput = document.querySelector("[data-filter-search]");
  const statusInput = document.querySelector("[data-filter-status]");
  const unrenderedTotalInput = document.querySelector("[data-unrendered-total]");
  const searchValue = (searchInput?.value || "").trim().toLowerCase();
  const statusValue = statusInput?.value || "all";
  let total = Number(unrenderedTotalInput?.value || 0);
  let visibleCount = 0;
  let editedCount = 0;

  document.querySelectorAll("[data-row]").forEach((row) => {
    const state = readRowState(row);
    const amount = calculateAmount(state);
    const visible = matchesFilters(state, searchValue, statusValue);

    total += amount;
    if (visible) visibleCount += 1;
    if (isEdited(state)) editedCount += 1;
    renderRow(state, amount, visible);
  });

  const grandTotalEl = document.getElementById("grand-total");
  const topTotalEl = document.getElementById("top-total");

  if (grandTotalEl.dataset.prevTotal && grandTotalEl.dataset.prevTotal !== String(total)) {
    [grandTotalEl, topTotalEl].forEach(el => {
      el.classList.remove("value-flash");
      void el.offsetWidth; // Trigger reflow
      el.classList.add("value-flash");
    });
  }
  grandTotalEl.dataset.prevTotal = total;

  grandTotalEl.textContent = formatter.format(total);
  topTotalEl.textContent = formatter.format(total);
  document.querySelector("[data-visible-count]").textContent = formatter.format(visibleCount);
  document.querySelector("[data-edited-count]").textContent = formatter.format(editedCount);
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

function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

const saveToServer = debounce((state) => {
  const formData = new FormData();
  formData.append("row_id", state.rowId);
  formData.append("manual_adjustment", state.manualValue);
  formData.append("reason", state.reason);

  // Get year/month from the URL or hidden inputs if they exist
  const urlParams = new URLSearchParams(window.location.search);
  formData.append("year", urlParams.get("year") || document.querySelector('input[name="year"]')?.value);
  formData.append("month", urlParams.get("month") || document.querySelector('input[name="month"]')?.value);

  const statusIndicator = document.getElementById("save-status");
  if (statusIndicator) statusIndicator.textContent = "正在儲存...";

  fetch("/adjustments/save", {
    method: "POST",
    body: formData,
  })
    .then((response) => {
      if (!response.ok) throw new Error("Save failed");
      if (statusIndicator) {
        statusIndicator.textContent = "已儲存";
        setTimeout(() => { if (statusIndicator.textContent === "已儲存") statusIndicator.textContent = ""; }, 2000);
      }
    })
    .catch((err) => {
      console.error(err);
      if (statusIndicator) statusIndicator.textContent = "儲存失敗";
    });
}, 800);

function bindForecastTable() {
  document.querySelectorAll("[data-manual], [data-reason], [data-filter-search], [data-filter-status]").forEach((input) => {
    input.addEventListener("input", (e) => {
      recalculate();
      if (e.target.hasAttribute("data-manual") || e.target.hasAttribute("data-reason")) {
        const row = e.target.closest("[data-row]");
        const restoreBtn = row.querySelector("[data-restore]");
        if (restoreBtn) restoreBtn.hidden = e.target.hasAttribute("data-manual") && e.target.value === "";
        saveToServer(readRowState(row));
      }
    });
    input.addEventListener("change", recalculate);
  });

  document.querySelectorAll("[data-restore]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const row = btn.closest("[data-row]");
      const manualInput = row.querySelector("[data-manual]");
      manualInput.value = "";
      btn.hidden = true;
      recalculate();
      saveToServer(readRowState(row));
    });
  });

  // Click to select all for manual quantity inputs
  document.querySelectorAll("[data-manual]").forEach((input) => {
    input.addEventListener("focus", (e) => e.target.select());
  });

  document.getElementById("forecast-form").addEventListener("submit", validateBeforeSubmit);

  // Phase 4: Render sparklines on initial load
  renderAllSparklines();

  recalculate();
}

bindForecastTable();
