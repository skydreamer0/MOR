const formatter = new Intl.NumberFormat("zh-TW", { maximumFractionDigits: 0 });
const precisionFormatter = formatter;

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
    priceQuantity: Number(row.dataset.priceQuantity || 1),
    systemForecast: Number(row.dataset.systemQty || 0),
    actualQuantity: Number(row.dataset.actualQty || 0),
    budgetQuantity: Number(row.dataset.budget || 0),
    lmActual: Number(row.dataset.lmActual || 0),
    lmBudget: Number(row.dataset.lmBudget || 0),
    manualValue: manualInput.value,
    reason: reasonInput.value,
    excluded: row.dataset.excluded === "true",
  };
}

function updateRateElement(el, rateValue) {
  if (!el) return;
  el.textContent = rateValue.toFixed(1) + "%";
  el.classList.toggle("low", rateValue < 80);
  el.classList.toggle("high", rateValue >= 100);
}

function updateGapElement(el, gapValue) {
  if (!el) return;
  const isPositive = gapValue > 0;
  const isNegative = gapValue < 0;
  const sign = isPositive ? "+" : "";
  el.textContent = sign + formatter.format(gapValue);
  el.classList.toggle("positive", isPositive);
  el.classList.toggle("negative", isNegative);
}

function finalForecastQuantity(state) {
  return state.manualValue === "" ? state.systemForecast : Number(state.manualValue);
}

function calculateAmount(state) {
  const priceQuantity = state.priceQuantity > 0 ? state.priceQuantity : 1;
  return state.excluded || state.budgetQuantity <= 0 ? 0 : (finalForecastQuantity(state) / priceQuantity) * state.price;
}

function isEdited(state) {
  return state.manualValue !== "";
}

function hasInvalidManualQuantity(state) {
  return state.manualValue !== "" && (Number.isNaN(Number(state.manualValue)) || Number(state.manualValue) < 0);
}

// Single source of truth for row visibility. All four filter axes must pass for a row to show.
// Reads _customerFilter and _viewMode from module state (set at top of recalculate()).
function matchesFilters(state, searchValue, statusValue) {
  const matchesSearch = searchValue === "" || state.searchText.includes(searchValue);
  let matchesStatus = true;
  if (statusValue === "auto" || statusValue === "not_due") {
    matchesStatus = state.status === statusValue;
  } else if (statusValue === "edited") {
    matchesStatus = isEdited(state);
  }
  const matchesCustomer = _customerFilter === "" || state.row.dataset.customer === _customerFilter;
  const matchesView = _viewMode !== "anomaly" || state.row.dataset.risk === "high";
  return matchesSearch && matchesStatus && matchesCustomer && matchesView;
}

function renderRow(state, amount, visible) {
  const invalid = hasInvalidManualQuantity(state);
  state.row.classList.toggle("edited", isEdited(state));
  state.row.classList.toggle("invalid", invalid);
  state.row.hidden = !visible;

  const manualInput = state.row.querySelector("[data-manual]");
  manualInput.setAttribute("aria-invalid", invalid ? "true" : "false");

  const finalQty = finalForecastQuantity(state);

  // 差異 (最後預估 - 預算目標)
  const budget = Number(state.row.dataset.budget || 0);
  const gap = finalQty - budget;
  updateGapElement(state.row.querySelector("[data-diff-display] .gap-value"), gap);

  // 上月表現合一格 (達成% + GAP)
  const lmRate = state.lmBudget > 0 ? (state.lmActual / state.lmBudget) * 100 : 0;
  const lmGap = state.lmActual - state.lmBudget;
  updateRateElement(state.row.querySelector("[data-lm-perf-display] .rate"), lmRate);
  updateGapElement(state.row.querySelector("[data-lm-perf-display] .gap-value"), lmGap);

  state.row.querySelector("[data-final-forecast]").textContent = precisionFormatter.format(finalQty);
}

function recalculate() {
  const searchInput = document.querySelector("[data-filter-search]");
  const statusInput = document.querySelector("[data-filter-status]");
  const unrenderedTotalInput = document.querySelector("[data-unrendered-total]");
  const searchValue = (searchInput?.value || "").trim().toLowerCase();
  const statusValue = statusInput?.value || "all";
  // Sync module state from DOM before the visibility pass; [data-filter-customer] is on the customer <select> in forecast.html
  _customerFilter = document.querySelector("[data-filter-customer]")?.value || "";
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

  const topTotalEl = document.getElementById("top-total");

  if (topTotalEl.dataset.prevTotal && topTotalEl.dataset.prevTotal !== String(total)) {
    topTotalEl.classList.remove("value-flash");
    void topTotalEl.offsetWidth;
    topTotalEl.classList.add("value-flash");
  }
  topTotalEl.dataset.prevTotal = total;
  topTotalEl.textContent = formatter.format(total);
  document.querySelector("[data-visible-count]").textContent = formatter.format(visibleCount);
  const editedBadge = document.getElementById("edited-badge");
  if (editedBadge) editedBadge.hidden = editedCount === 0;
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

/* ── Row Detail Panel ────────────────────────────────────────────── */

let _detailRowId = null;

function openDetailPanel(row) {
  const panel   = document.getElementById("row-detail");
  const backdrop = document.getElementById("row-detail-backdrop");
  if (!panel || !backdrop) return;

  _detailRowId = row.dataset.rowId;

  const state    = readRowState(row);
  const f        = (n) => formatter.format(n);
  const fp       = (n) => precisionFormatter.format(n);
  const sign     = (n) => (n > 0 ? "+" : "") + fp(n);
  const pct      = (n) => n.toFixed(1) + "%";

  // Header
  document.getElementById("rd-customer").textContent = row.dataset.customer || "";
  document.getElementById("rd-product").textContent  = row.dataset.productName || "";

  // 上月表現
  const lmActual = state.lmActual;
  const lmBudget = state.lmBudget;
  const lmRate   = lmBudget > 0 ? (lmActual / lmBudget) * 100 : 0;
  const lmGap    = lmActual - lmBudget;
  document.getElementById("rd-lm-actual").textContent = fp(lmActual);
  document.getElementById("rd-lm-budget").textContent = fp(lmBudget);
  setDetailVal("rd-lm-rate", pct(lmRate), lmRate >= 100 ? "high" : lmRate < 80 ? "low" : "");
  setDetailVal("rd-lm-gap",  sign(lmGap), lmGap >= 0 ? "positive" : "negative");

  // 年度比較
  const lastYear = Number(row.dataset.lastYearQty || 0);
  const thisYear = Number(row.dataset.actualQty   || 0);
  document.getElementById("rd-last-year").textContent = fp(lastYear);
  document.getElementById("rd-this-year").textContent = fp(thisYear);

  // 預算達成 (動態，跟著人工調整更新)
  refreshDetailBudget(state);

  // 展開
  document.querySelectorAll("tr.row-detail-active").forEach(r => r.classList.remove("row-detail-active"));
  row.classList.add("row-detail-active");

  panel.hidden   = false;
  backdrop.hidden = false;
  requestAnimationFrame(() => {
    panel.classList.add("open");
    backdrop.classList.add("open");
  });
}

function refreshDetailBudget(state) {
  const fp      = (n) => precisionFormatter.format(n);
  const pct     = (n) => n.toFixed(1) + "%";
  const sign    = (n) => (n > 0 ? "+" : "") + fp(n);

  const budget   = state.budgetQuantity;
  const finalQty = finalForecastQuantity(state);
  const diff     = finalQty - budget;
  const rate     = budget > 0 ? (finalQty / budget) * 100 : 0;
  const amount   = calculateAmount(state);
  const included = state.excluded ? "排除" : (budget <= 0 ? "預算為 0" : "納入");

  document.getElementById("rd-budget").textContent = fp(budget);
  document.getElementById("rd-final").textContent  = fp(finalQty);
  setDetailVal("rd-achieve-rate", pct(rate), rate >= 100 ? "high" : rate < 80 ? "low" : "");
  setDetailVal("rd-diff",         sign(diff), diff >= 0 ? "positive" : "negative");
  document.getElementById("rd-amount").textContent   = formatter.format(amount);
  document.getElementById("rd-included").textContent = included;
}

function setDetailVal(id, text, cls) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = text;
  el.className = "detail-val" + (cls ? " " + cls : "");
}

function closeDetailPanel() {
  const panel    = document.getElementById("row-detail");
  const backdrop = document.getElementById("row-detail-backdrop");
  if (!panel || !backdrop) return;

  panel.classList.remove("open");
  backdrop.classList.remove("open");
  document.querySelectorAll("tr.row-detail-active").forEach(r => r.classList.remove("row-detail-active"));
  _detailRowId = null;

  panel.addEventListener("transitionend", () => {
    panel.hidden    = true;
    backdrop.hidden = true;
  }, { once: true });
}

/* ── View Toggle (只看異常 / 全部明細) ──────────────────────────── */

// All row visibility goes through recalculate() — do not manipulate row.hidden or style.display elsewhere.
// _viewMode and _customerFilter are read inside matchesFilters(); update them before calling recalculate().
let _viewMode = "anomaly";
let _customerFilter = "";

function applyViewMode(mode) {
  // Previously used forEach + classList.toggle("forecast-table__row--collapsed"); now delegates to recalculate()
  // so view mode, customer filter, search, and status all go through one visibility pass.
  _viewMode = mode;
  document.getElementById("btn-anomaly-only")?.classList.toggle("active", mode === "anomaly");
  document.getElementById("btn-show-all")?.classList.toggle("active", mode === "all");
  recalculate();
}

/* ── Main bind ───────────────────────────────────────────────────── */

function bindForecastTable() {
  // [data-filter-customer] replaces the old onchange="filterRows()" on the customer <select>
  document.querySelectorAll("[data-manual], [data-reason], [data-filter-search], [data-filter-status], [data-filter-customer]").forEach((input) => {
    input.addEventListener("input", (e) => {
      recalculate();
      if (e.target.hasAttribute("data-manual") || e.target.hasAttribute("data-reason")) {
        const row = e.target.closest("[data-row]");
        const restoreBtn = row.querySelector("[data-restore]");
        if (restoreBtn) restoreBtn.hidden = e.target.hasAttribute("data-manual") && e.target.value === "";
        saveToServer(readRowState(row));
        // refresh side panel if open for this row
        if (_detailRowId && _detailRowId === row.dataset.rowId) {
          refreshDetailBudget(readRowState(row));
        }
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
      if (_detailRowId && _detailRowId === row.dataset.rowId) {
        refreshDetailBudget(readRowState(row));
      }
    });
  });

  document.querySelectorAll("[data-manual]").forEach((input) => {
    input.addEventListener("focus", (e) => e.target.select());
  });

  // Row click → open detail panel
  document.querySelectorAll("tr[data-row]").forEach((tr) => {
    tr.addEventListener("click", (e) => {
      if (e.target.closest("input, button, a, label")) return;
      if (_detailRowId === tr.dataset.rowId) {
        closeDetailPanel();
      } else {
        openDetailPanel(tr);
      }
    });
  });

  // Detail panel close
  document.getElementById("rd-close")?.addEventListener("click", closeDetailPanel);
  document.getElementById("row-detail-backdrop")?.addEventListener("click", closeDetailPanel);

  // View toggle
  const highRiskCount = document.querySelectorAll("tr[data-risk='high']").length;
  const totalRows     = document.querySelectorAll("tr[data-risk]").length;

  if (highRiskCount > 0 && totalRows > highRiskCount) {
    applyViewMode("anomaly");
  } else {
    // All rows are same risk level, default to show all
    applyViewMode("all");
    document.querySelector(".view-toggle")?.style.setProperty("display", "none");
  }

  document.getElementById("btn-anomaly-only")?.addEventListener("click", () => applyViewMode("anomaly"));
  document.getElementById("btn-show-all")?.addEventListener("click",     () => applyViewMode("all"));

  document.getElementById("forecast-form").addEventListener("submit", validateBeforeSubmit);

  renderAllSparklines();
  recalculate();
}

bindForecastTable();


/* ── Snapshot Modal Logic ───────────────────────────────────── */

function showSnapshotModal(snapshotType) {
  const year = document.querySelector('input[name="year"]')?.value;
  const month = document.querySelector('input[name="month"]')?.value;
  const isFinalize = snapshotType === "Final";
  const defaultName = isFinalize
    ? `定稿 ${year}/${String(month).padStart(2, "0")}`
    : `草稿 ${year}/${String(month).padStart(2, "0")}`;

  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop";
  backdrop.innerHTML = `
    <div class="modal-card">
      <h2>${isFinalize ? "確認定稿" : "儲存草稿"}</h2>
      ${isFinalize ? '<p style="color: var(--danger); font-weight: 600; margin: 0 0 16px 0;">定稿後將無法再修改本月預估。</p>' : ""}
      <label>
        版本名稱
        <input type="text" id="snapshot-name-input" value="${defaultName}" placeholder="請輸入版本名稱">
      </label>
      <div class="modal-actions">
        <button type="button" class="btn-secondary" id="modal-cancel">取消</button>
        <button type="button" class="${isFinalize ? "btn-danger" : ""}" id="modal-confirm">
          ${isFinalize ? "確認定稿" : "儲存"}
        </button>
      </div>
    </div>
  `;

  document.body.appendChild(backdrop);
  const nameInput = backdrop.querySelector("#snapshot-name-input");
  nameInput.select();

  backdrop.querySelector("#modal-cancel").addEventListener("click", () => backdrop.remove());
  backdrop.addEventListener("click", (e) => { if (e.target === backdrop) backdrop.remove(); });

  backdrop.querySelector("#modal-confirm").addEventListener("click", () => {
    const form = document.createElement("form");
    form.method = "POST";
    form.action = "/snapshots/save";
    form.style.display = "none";

    const fields = {
      year: year,
      month: month,
      snapshot_name: nameInput.value.trim() || defaultName,
      snapshot_type: snapshotType,
    };

    for (const [key, value] of Object.entries(fields)) {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = key;
      input.value = value;
      form.appendChild(input);
    }

    document.body.appendChild(form);
    form.submit();
  });
}

document.getElementById("btn-save-snapshot")?.addEventListener("click", () => showSnapshotModal("Draft"));
document.getElementById("btn-finalize")?.addEventListener("click", () => showSnapshotModal("Final"));
