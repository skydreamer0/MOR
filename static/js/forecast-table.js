const formatter = new Intl.NumberFormat("zh-TW", { maximumFractionDigits: 0 });
const precisionFormatter = formatter;

const _fp   = (n) => precisionFormatter.format(n);
const _pct  = (n) => n.toFixed(1) + "%";
const _sign = (n) => (n > 0 ? "+" : "") + _fp(n);

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

  // Determine trend colour: compare last vs first non-zero.
  // Taiwan convention: 漲=紅 (#dc2626)，跌=綠 (#047857)
  const first = data.find((v) => v > 0) ?? 0;
  const last = data[data.length - 1];
  const trendUp = last >= first;
  const lineColor = trendUp
    ? "rgba(220, 38, 38, 0.7)"  // danger  — 漲
    : "rgba(4, 120, 87, 0.7)";  // success — 跌
  const dotColor = trendUp
    ? "rgb(220, 38, 38)"
    : "rgb(4, 120, 87)";
  const fillColor = trendUp
    ? "rgba(220, 38, 38, 0.06)"
    : "rgba(4, 120, 87, 0.06)";

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
      const trend = readRowPayload(row).trend || [];
      drawSparkline(canvas, trend);
    } catch {
      // Silently skip if data is malformed
    }
  });
}


/* ── Core Table Logic ───────────────────────────────────────────── */

function readRowPayload(row) {
  try {
    return JSON.parse(row.dataset.state || "{}");
  } catch {
    return {};
  }
}

function readRowState(row) {
  const manualInput = row.querySelector("[data-manual]");
  const reasonInput = row.querySelector("[data-reason]");
  const payload = readRowPayload(row);
  return {
    row,
    rowId: row.dataset.rowId,
    status: row.dataset.status,
    searchText: (row.dataset.search || "").toLowerCase(),
    price: Number(payload.price || 0),
    priceQuantity: Number(payload.price_quantity || 1),
    systemForecast: Number(payload.system_forecast || 0),
    actualQuantity: Number(payload.actual_quantity || 0),
    budgetQuantity: Number(payload.budget_quantity || 0),
    lmActual: Number(payload.lm_actual || 0),
    lmBudget: Number(payload.lm_budget || 0),
    manualValue: manualInput.value,
    reason: reasonInput.value,
    excluded: payload.excluded === true,
    payload,
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
  // 方向性指標使用台灣慣例：漲=紅(.rising)、跌=綠(.falling)
  el.classList.toggle("rising",  isPositive);
  el.classList.toggle("falling", isNegative);
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
  const budget = state.budgetQuantity;
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
let _detailReturnFocusEl = null;

function openDetailPanel(row) {
  const panel   = document.getElementById("row-detail");
  const backdrop = document.getElementById("row-detail-backdrop");
  if (!panel || !backdrop) return;

  _detailRowId = row.dataset.rowId;
  _detailReturnFocusEl = row.querySelector("[data-manual]") || null;

  const state = readRowState(row);

  // Header
  document.getElementById("rd-customer").textContent = row.dataset.customer || "";
  document.getElementById("rd-product").textContent  = row.dataset.productName || "";

  // 上月表現 — 兩者都是 0 時整個 section 無意義，直接隱藏
  const lmActual = state.lmActual;
  const lmBudget = state.lmBudget;
  const lmSection = document.getElementById("rd-lm-section");
  if (lmSection) lmSection.hidden = lmActual === 0 && lmBudget === 0;

  const lmRate = lmBudget > 0 ? (lmActual / lmBudget) * 100 : 0;
  const lmGap  = lmActual - lmBudget;
  document.getElementById("rd-lm-actual").textContent = _fp(lmActual);
  document.getElementById("rd-lm-budget").textContent = _fp(lmBudget);
  setDetailVal("rd-lm-rate", _pct(lmRate), lmRate >= 100 ? "high" : lmRate < 80 ? "low" : "");
  setDetailVal("rd-lm-gap",  _sign(lmGap), lmGap >= 0 ? "rising" : "falling");

  // 年度業績比較：趨勢圖 + 月份表格 + YTD + 評估
  renderAnalytics(row);

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
    document.getElementById("rd-close")?.focus();
  });
}

function refreshDetailBudget(state) {
  const budget   = state.budgetQuantity;
  const finalQty = finalForecastQuantity(state);
  const diff     = finalQty - budget;
  const rate     = budget > 0 ? (finalQty / budget) * 100 : 0;
  const amount   = calculateAmount(state);

  document.getElementById("rd-budget").textContent = _fp(budget);
  document.getElementById("rd-final").textContent  = _fp(finalQty);
  setDetailVal("rd-achieve-rate", _pct(rate), rate >= 100 ? "high" : rate < 80 ? "low" : "");
  setDetailVal("rd-diff",         _sign(diff), diff >= 0 ? "rising" : "falling");
  document.getElementById("rd-amount").textContent = formatter.format(amount);

  // 計算狀態 badge（放在 section header 旁）
  const badge = document.getElementById("rd-included-badge");
  if (badge) {
    const isExcluded = state.excluded;
    const noBudget   = budget <= 0;
    badge.textContent = isExcluded ? "排除" : (noBudget ? "缺預算" : "納入");
    badge.className   = "badge" + (isExcluded || noBudget ? " off" : "");
    badge.hidden      = false;
  }
}

function setDetailVal(id, text, cls) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = text;
  el.className = "detail-val" + (cls ? " " + cls : "");
}

function renderAnalytics(row) {
  const panel = document.getElementById("row-detail");
  const targetMonth = Number(panel?.dataset.forecastMonth || 0);

  const payload = readRowPayload(row);
  const lyMonthly     = payload.ly_monthly || [];
  const tyMonthly     = payload.ty_monthly || [];
  const budgetMonthly = payload.budget_monthly || [];
  const lyPrice       = Number(payload.ly_price || 0);
  const tyPrice       = Number(payload.price || 0);

  const data = { lyMonthly, tyMonthly, budgetMonthly, targetMonth };

  // Trend chart
  AnalyticsRenderer.renderTrendChart(
    document.getElementById("rd-trend-canvas"),
    data,
  );

  // Monthly table (6-column)
  AnalyticsRenderer.renderMonthlyTable(
    document.getElementById("rd-monthly-tbody"),
    data,
    {
      lyTotalId:         "rd-ly-total",
      budgetTotalId:     "rd-budget-total",
      tyTotalId:         "rd-ty-total",
      budgetRateTotalId: "rd-budget-rate-total",
      yoyTotalId:        "rd-yoy-total",
    },
  );

  // Compute shared metrics for YTD + assessment
  const metrics = AnalyticsRenderer.computeMetrics(lyMonthly, tyMonthly, budgetMonthly, targetMonth);

  // YTD cumulative
  AnalyticsRenderer.renderYtd(
    document.getElementById("rd-ytd-container"),
    metrics,
    targetMonth,
  );

  // Assessment: MA3, MA6, trend
  AnalyticsRenderer.renderAssessment(
    document.getElementById("rd-assessment-container"),
    metrics,
  );

  // Price section
  const moneyFmt = (n) => n > 0 ? formatter.format(n) : "—";
  document.getElementById("rd-ly-price").textContent = moneyFmt(lyPrice);
  document.getElementById("rd-ty-price").textContent = moneyFmt(tyPrice);

  const priceChangeRow = document.getElementById("rd-price-change-row");
  if (priceChangeRow && lyPrice > 0 && tyPrice > 0 && Math.abs(tyPrice - lyPrice) > 0.01) {
    const pct = (tyPrice - lyPrice) / lyPrice * 100;
    setDetailVal("rd-price-change", (pct > 0 ? "+" : "") + pct.toFixed(1) + "%",
      pct > 0 ? "rising" : "falling");   // 漲價=紅、跌價=綠（台灣慣例）
    priceChangeRow.hidden = false;
  } else if (priceChangeRow) {
    priceChangeRow.hidden = true;
  }
}

function closeDetailPanel() {
  const panel    = document.getElementById("row-detail");
  const backdrop = document.getElementById("row-detail-backdrop");
  if (!panel || !backdrop) return;

  panel.classList.remove("open");
  backdrop.classList.remove("open");
  document.querySelectorAll("tr.row-detail-active").forEach(r => r.classList.remove("row-detail-active"));
  _detailRowId = null;
  _detailReturnFocusEl?.focus();
  _detailReturnFocusEl = null;

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

function markForecastBound(element, attribute = "data-forecast-bound") {
  if (!element || element.hasAttribute(attribute)) return false;
  element.setAttribute(attribute, "true");
  return true;
}

function handleEditableInput(event) {
  recalculate();
  if (!event.target.hasAttribute("data-manual") && !event.target.hasAttribute("data-reason")) return;

  const row = event.target.closest("[data-row]");
  const restoreBtn = row.querySelector("[data-restore]");
  if (restoreBtn) restoreBtn.hidden = event.target.hasAttribute("data-manual") && event.target.value === "";
  saveToServer(readRowState(row));
  // refresh side panel if open for this row
  if (_detailRowId && _detailRowId === row.dataset.rowId) {
    refreshDetailBudget(readRowState(row));
  }
}

function bindForecastRow(row) {
  row.querySelectorAll("[data-manual], [data-reason]").forEach((input) => {
    if (!markForecastBound(input)) return;
    input.addEventListener("input", handleEditableInput);
    input.addEventListener("change", recalculate);
  });

  row.querySelectorAll("[data-restore]").forEach((btn) => {
    if (!markForecastBound(btn)) return;
    btn.addEventListener("click", () => {
      const currentRow = btn.closest("[data-row]");
      const manualInput = currentRow.querySelector("[data-manual]");
      manualInput.value = "";
      btn.hidden = true;
      recalculate();
      saveToServer(readRowState(currentRow));
      if (_detailRowId && _detailRowId === currentRow.dataset.rowId) {
        refreshDetailBudget(readRowState(currentRow));
      }
    });
  });

  row.querySelectorAll("[data-manual]").forEach((input) => {
    if (!markForecastBound(input, "data-forecast-focus-bound")) return;
    input.addEventListener("focus", (event) => event.target.select());
  });

  if (markForecastBound(row, "data-forecast-row-bound")) {
    row.addEventListener("click", (event) => {
      if (event.target.closest("input, button, a, label")) return;
      if (_detailRowId === row.dataset.rowId) {
        closeDetailPanel();
      } else {
        openDetailPanel(row);
      }
    });
  }
}

function bindForecastControls() {
  // [data-filter-customer] replaces the old onchange="filterRows()" on the customer <select>
  document.querySelectorAll("[data-filter-search], [data-filter-status], [data-filter-customer]").forEach((input) => {
    if (!markForecastBound(input)) return;
    input.addEventListener("input", recalculate);
    input.addEventListener("change", recalculate);
  });

  const closeButton = document.getElementById("rd-close");
  if (closeButton && markForecastBound(closeButton)) {
    closeButton.addEventListener("click", closeDetailPanel);
  }
  const backdrop = document.getElementById("row-detail-backdrop");
  if (backdrop && markForecastBound(backdrop)) {
    backdrop.addEventListener("click", closeDetailPanel);
  }

  if (markForecastBound(document.body, "data-forecast-detail-escape-bound")) {
    document.addEventListener("keydown", (e) => {
      if (e.key !== "Escape") return;
      const panel = document.getElementById("row-detail");
      if (panel && !panel.hidden) closeDetailPanel();
    });
  }

  const anomalyButton = document.getElementById("btn-anomaly-only");
  if (anomalyButton && markForecastBound(anomalyButton)) {
    anomalyButton.addEventListener("click", () => applyViewMode("anomaly"));
  }
  const showAllButton = document.getElementById("btn-show-all");
  if (showAllButton && markForecastBound(showAllButton)) {
    showAllButton.addEventListener("click", () => applyViewMode("all"));
  }

  const form = document.getElementById("forecast-form");
  if (form && markForecastBound(form)) {
    form.addEventListener("submit", validateBeforeSubmit);
  }
}

function bindForecastRows(root = document) {
  root.querySelectorAll("tr[data-row]").forEach(bindForecastRow);
}

function bindHtmxRowSwapHandler() {
  if (!markForecastBound(document.body, "data-forecast-htmx-bound")) return;
  document.body.addEventListener("htmx:afterSwap", (event) => {
    const swapped = event.detail?.elt;
    if (!swapped) return;

    const rows = swapped.matches?.("tr[data-row]")
      ? [swapped]
      : Array.from(swapped.querySelectorAll?.("tr[data-row]") || []);
    if (rows.length === 0) return;

    rows.forEach(bindForecastRow);
    renderAllSparklines();
    recalculate();

    const activeRow = rows.find((row) => row.dataset.rowId === _detailRowId);
    if (activeRow) {
      activeRow.classList.add("row-detail-active");
      refreshDetailBudget(readRowState(activeRow));
    }
  });
}

function visibleDataRows() {
  return Array.from(document.querySelectorAll("[data-row]"))
    .filter((row) => row.style.display !== "none" && !row.hidden);
}

function bindKeyboardNavigation() {
  if (!markForecastBound(document.body, "data-forecast-keyboard-bound")) return;
  document.addEventListener("keydown", (e) => {
    const input = e.target instanceof Element ? e.target.closest("[data-manual]") : null;
    if (!input) return;

    if (e.key === "Escape") {
      const restore = input.closest("[data-row]")?.querySelector("[data-restore]");
      if (restore && !restore.hidden) restore.click();
      return;
    }

    if (e.key !== "Enter" && e.key !== "ArrowDown" && e.key !== "ArrowUp") return;

    e.preventDefault();
    const rows = visibleDataRows();
    const row = input.closest("[data-row]");
    const index = rows.indexOf(row);
    if (index === -1) return;

    const targetIndex = e.key === "ArrowUp" ? index - 1 : index + 1;
    const target = rows[targetIndex]?.querySelector("[data-manual]");
    if (!target) return;

    target.focus();
    target.select();
  });
}

function bindForecastTable() {
  bindForecastControls();
  bindForecastRows();
  bindHtmxRowSwapHandler();
  bindKeyboardNavigation();

  const highRiskCount = document.querySelectorAll("tr[data-risk='high']").length;
  const totalRows     = document.querySelectorAll("tr[data-risk]").length;

  if (highRiskCount > 0 && totalRows > highRiskCount) {
    applyViewMode("anomaly");
  } else {
    // All rows are same risk level, default to show all
    applyViewMode("all");
    document.querySelector(".view-toggle")?.style.setProperty("display", "none");
  }

  renderAllSparklines();
  recalculate();
}

if (typeof document !== "undefined") {
  bindForecastTable();
}


/* ── Snapshot Modal Logic ───────────────────────────────────── */

function showSnapshotModal(snapshotType) {
  const triggerEl = document.activeElement;
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

  const closeModal = () => {
    backdrop.remove();
    document.removeEventListener("keydown", onKeydown);
    triggerEl?.focus();
  };
  const onKeydown = (e) => { if (e.key === "Escape") closeModal(); };
  document.addEventListener("keydown", onKeydown);

  backdrop.querySelector("#modal-cancel").addEventListener("click", closeModal);
  backdrop.addEventListener("click", (e) => { if (e.target === backdrop) closeModal(); });

  backdrop.querySelector("#modal-confirm").addEventListener("click", async () => {
    if (isFinalize && window.appConfirm) {
      const ok = await window.appConfirm({
        title: "定稿本月預估",
        message: "定稿後本月預估將鎖定，無法再調整。",
        okLabel: "定稿",
      });
      if (!ok) return;
    }

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

if (typeof document !== "undefined") {
  document.getElementById("btn-save-snapshot")?.addEventListener("click", () => showSnapshotModal("Draft"));
  document.getElementById("btn-finalize")?.addEventListener("click", () => showSnapshotModal("Final"));
}

if (typeof module === "object" && module.exports) {
  module.exports = {
    readRowPayload,
    readRowState,
    finalForecastQuantity,
    calculateAmount,
    hasInvalidManualQuantity,
  };
}
