/**
 * analytics-renderer.js — shared analytics rendering layer
 *
 * All functions are pure: they take data arrays and DOM targets,
 * and produce consistent UI.  No global state.
 *
 * Used by:
 *   forecast-table.js  — row detail sidebar
 *   dashboard pages    — future customer / product analytics panels
 *
 * Colour palette mirrors mor.css design tokens (hard-coded here to avoid
 * a CSS-variable lookup on every canvas paint):
 *   teal  #0d9488   this year
 *   slate #64748b   last year
 *   amber #d97706   budget
 */

const AnalyticsRenderer = (() => {
  "use strict";

  // ── Formatters ─────────────────────────────────────────────────────────────
  // Semantic formatting (signs, 達成率四階 class, 漲跌 class) lives in fmt.js.
  // Loaded as a plain <script> (no build step, ADR-0001); require() is the node:test path.
  const fmt = typeof AnalyticsFmt !== "undefined" ? AnalyticsFmt : require("./fmt.js");

  const fmt0 = new Intl.NumberFormat("zh-TW", { maximumFractionDigits: 0 });
  const fmt1 = new Intl.NumberFormat("zh-TW", { maximumFractionDigits: 1 });
  const fmt2 = new Intl.NumberFormat("zh-TW", { maximumFractionDigits: 2, minimumFractionDigits: 0 });

  const MONTHS = ["1月","2月","3月","4月","5月","6月","7月","8月","9月","10月","11月","12月"];

  const COLOR_TY   = "#0d9488";
  const COLOR_LY   = "rgba(100,116,139,0.65)";
  const COLOR_BUD  = "#d97706";
  const COLOR_MA3  = "#f97316";   // orange  — short-term MA
  const COLOR_MA6  = "#a78bfa";   // lavender — medium-term MA


  // ── setupCanvas ────────────────────────────────────────────────────────────
  /**
   * HiDPI canvas boilerplate, extracted from the three call sites that used to
   * repeat it (renderTrendChart / renderSparklineInCanvas / forecast-table.js
   * drawSparkline). Sizes the backing store by devicePixelRatio and returns a
   * context pre-scaled so all drawing code can keep working in CSS pixels.
   *
   * Width/height come from `clientWidth`/`clientHeight`; the fallbacks are per
   * call site because each canvas has its own intrinsic size, and they are only
   * reached when the element is not laid out yet (hidden ancestor → 0).
   *
   * Note: assigning `canvas.width` already clears the surface; call sites that
   * still call `clearRect` afterwards keep doing so — it is a no-op safeguard.
   *
   * @param {HTMLCanvasElement|null} canvas
   * @param {number} fallbackW  CSS-pixel width used when clientWidth is 0
   * @param {number} fallbackH  CSS-pixel height used when clientHeight is 0
   * @returns {{ctx: CanvasRenderingContext2D, w: number, h: number}|null}
   */
  function setupCanvas(canvas, fallbackW, fallbackH) {
    if (!canvas) return null;
    const dpr = (typeof window !== "undefined" && window.devicePixelRatio) || 1;
    const w = canvas.clientWidth  || fallbackW;
    const h = canvas.clientHeight || fallbackH;
    canvas.width  = w * dpr;
    canvas.height = h * dpr;
    const ctx = canvas.getContext("2d");
    ctx.scale(dpr, dpr);
    return { ctx, w, h };
  }


  // ── computeMetrics ─────────────────────────────────────────────────────────
  /**
   * @param {number[]} lyMonthly      [12] last year monthly quantities
   * @param {number[]} tyMonthly      [12] this year confirmed actual quantities
   * @param {number[]} budgetMonthly  [12] budget targets
   * @param {number}   targetMonth    1-based forecast month (used for MA windows)
   * @param {number}   [lastActualMonth]  1-based last month with confirmed data;
   *                                      defaults to targetMonth when omitted
   * @returns {object} pre-computed metrics object
   */
  function computeMetrics(lyMonthly, tyMonthly, budgetMonthly, targetMonth, lastActualMonth) {
    // YTD is always based on confirmed actuals only
    const ytdCutoff = (lastActualMonth != null && lastActualMonth > 0)
      ? lastActualMonth : targetMonth;

    const ytdLy     = _sum(lyMonthly.slice(0, ytdCutoff));
    const ytdTy     = _sum(tyMonthly.slice(0, ytdCutoff));
    const ytdBudget = _sum(budgetMonthly.slice(0, ytdCutoff));

    const ytdGapVsLy    = ytdTy - ytdLy;
    const ytdRateVsLy   = ytdLy   > 0 ? ytdTy / ytdLy   * 100 : 0;
    const ytdBudgetRate = ytdBudget > 0 ? ytdTy / ytdBudget * 100 : 0;

    // MA windows: months BEFORE targetMonth (already elapsed)
    const elapsed = targetMonth - 1;
    const recent3 = tyMonthly.slice(Math.max(0, elapsed - 3), elapsed);
    const prev3   = tyMonthly.slice(Math.max(0, elapsed - 6), Math.max(0, elapsed - 3));
    const recent6 = tyMonthly.slice(Math.max(0, elapsed - 6), elapsed);

    const ma3 = _avg(recent3);
    const ma6 = _avg(recent6);

    const r3 = _avg(recent3.filter(v => v > 0));
    const p3 = _avg(prev3.filter(v => v > 0));
    let trendDir = "flat";
    if (p3 > 0) {
      const ratio = r3 / p3;
      if (ratio >= 1.05) trendDir = "up";
      else if (ratio <= 0.95) trendDir = "down";
    }

    return {
      ytdLy, ytdTy, ytdBudget,
      ytdGapVsLy, ytdRateVsLy, ytdBudgetRate,
      ma3, ma6, trendDir,
      ytdCutoff,
    };
  }


  // ── renderTrendChart ───────────────────────────────────────────────────────
  /**
   * Draw a 3-line trend chart on a <canvas> element.
   * @param {HTMLCanvasElement} canvas
   * @param {object} data  { lyMonthly, tyMonthly, budgetMonthly, targetMonth,
   *                         forecastMonthly?, lastActualMonth? }
   *   forecastMonthly: [12] with a non-zero value only at targetMonth-1
   *   lastActualMonth: 1-based last month with confirmed actual data
   */
  function renderTrendChart(canvas, { lyMonthly, tyMonthly, budgetMonthly, targetMonth,
                                      forecastMonthly, lastActualMonth }) {
    const surface = setupCanvas(canvas, 340, 110);
    if (!surface) return;
    const { ctx, w, h } = surface;
    ctx.clearRect(0, 0, w, h);

    const padL = 6, padR = 6, padT = 12, padB = 18;
    const plotW = w - padL - padR;
    const plotH = h - padT - padB;

    const fcstVal = (forecastMonthly && forecastMonthly[targetMonth - 1]) || 0;

    // Y scale across all series including forecast value
    const allVals = [...lyMonthly, ...tyMonthly, ...budgetMonthly,
                     fcstVal > 0 ? fcstVal : 0].filter(v => v > 0);
    if (allVals.length === 0) return;
    const maxVal = Math.max(...allVals);
    const minVal = 0;
    const range  = maxVal - minVal || 1;

    const xOf = (i) => padL + (i / 11) * plotW;
    const yOf = (v) => padT + plotH - ((v - minVal) / range) * plotH;

    // Current-month vertical guide
    if (targetMonth >= 1 && targetMonth <= 12) {
      const mx = xOf(targetMonth - 1);
      ctx.save();
      ctx.setLineDash([3, 3]);
      ctx.strokeStyle = "rgba(100,116,139,0.25)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(mx, padT);
      ctx.lineTo(mx, padT + plotH);
      ctx.stroke();
      ctx.restore();
    }

    // Budget line (dashed amber)
    if (budgetMonthly.some(v => v > 0)) {
      _drawLine(ctx, budgetMonthly, 12, xOf, yOf, COLOR_BUD, 1.5, [4, 3]);
    }

    // Last year line (slate, full 12M)
    _drawLine(ctx, lyMonthly, 12, xOf, yOf, COLOR_LY, 1.5);

    // MA6 line (lavender dashed) — drawn before MA3 so MA3 renders on top
    const ma6arr = _rollingMA(lyMonthly, tyMonthly, 6, targetMonth);
    if (ma6arr.some(v => v !== null)) {
      _drawLineMasked(ctx, ma6arr, xOf, yOf, COLOR_MA6, 1.2, [3, 3]);
    }

    // MA3 line (orange dashed)
    const ma3arr = _rollingMA(lyMonthly, tyMonthly, 3, targetMonth);
    if (ma3arr.some(v => v !== null)) {
      _drawLineMasked(ctx, ma3arr, xOf, yOf, COLOR_MA3, 1.2, [3, 3]);
    }

    // This year actual line (teal solid, ends at lastActualMonth)
    const actualCutoff = (lastActualMonth != null && lastActualMonth > 0)
      ? lastActualMonth : targetMonth;
    const tyMasked = tyMonthly.map((v, i) => (i < actualCutoff ? v : null));
    _drawLineMasked(ctx, tyMasked, xOf, yOf, COLOR_TY, 2);

    // Forecast projection: dashed segment from last actual point → forecast point
    if (fcstVal > 0 && actualCutoff < targetMonth) {
      const lastActVal = tyMonthly[actualCutoff - 1] || 0;
      ctx.save();
      ctx.setLineDash([4, 3]);
      ctx.strokeStyle = COLOR_TY;
      ctx.globalAlpha = 0.55;
      ctx.lineWidth = 1.5;
      ctx.lineJoin = "round";
      ctx.beginPath();
      ctx.moveTo(xOf(actualCutoff - 1), yOf(lastActVal));
      ctx.lineTo(xOf(targetMonth - 1), yOf(fcstVal));
      ctx.stroke();
      // Open circle at forecast point
      ctx.setLineDash([]);
      ctx.globalAlpha = 0.75;
      ctx.beginPath();
      ctx.arc(xOf(targetMonth - 1), yOf(fcstVal), 3.5, 0, Math.PI * 2);
      ctx.strokeStyle = COLOR_TY;
      ctx.lineWidth = 1.5;
      ctx.stroke();
      ctx.restore();
    }

    // X-axis month labels (every other month)
    ctx.fillStyle = "rgba(100,116,139,0.75)";
    ctx.font = `9px Inter, "Microsoft JhengHei", sans-serif`;
    ctx.textAlign = "center";
    [0, 2, 4, 6, 8, 10].forEach(i => {
      ctx.fillText(`${i + 1}`, xOf(i), h - 3);
    });
  }

  function _drawLine(ctx, data, count, xOf, yOf, color, width, dash = []) {
    const pts = data.slice(0, count).map((v, i) => ({ x: xOf(i), y: yOf(v || 0) }));
    if (pts.length === 0) return;
    ctx.save();
    ctx.setLineDash(dash);
    ctx.strokeStyle = color;
    ctx.lineWidth   = width;
    ctx.lineJoin    = "round";
    ctx.beginPath();
    pts.forEach((p, i) => (i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y)));
    ctx.stroke();
    ctx.restore();
  }

  function _drawLineMasked(ctx, data, xOf, yOf, color, width, dash = []) {
    // data may contain nulls — draw only contiguous non-null segments
    const pts = data.map((v, i) => (v !== null ? { x: xOf(i), y: yOf(v) } : null));
    if (pts.every(p => p === null)) return;
    ctx.save();
    ctx.setLineDash(dash);
    ctx.strokeStyle = color;
    ctx.lineWidth   = width;
    ctx.lineJoin    = "round";
    ctx.beginPath();
    let penDown = false;
    pts.forEach(p => {
      if (!p) { penDown = false; return; }
      if (!penDown) { ctx.moveTo(p.x, p.y); penDown = true; }
      else ctx.lineTo(p.x, p.y);
    });
    ctx.stroke();
    ctx.setLineDash([]);
    // Terminal dot only for solid lines (MA lines get no dot)
    if (dash.length === 0) {
      const last = pts.filter(Boolean).pop();
      if (last) {
        ctx.beginPath();
        ctx.arc(last.x, last.y, 3, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
      }
    }
    ctx.restore();
  }


  // ── renderMonthlyTable ─────────────────────────────────────────────────────
  /**
   * Populate <tbody> with monthly rows.
   * Expects 6-column table: 月 | 去年 | 預算 | 今年 | 達成% | YoY%
   * Also sets totals by ID on tfoot cells.
   * @param {HTMLElement} tbody
   * @param {object} data  { lyMonthly, tyMonthly, budgetMonthly, targetMonth }
   * @param {object} totals  { lyTotalId, budgetTotalId, tyTotalId, budgetRateTotalId, yoyTotalId }
   */
  function renderMonthlyTable(tbody, { lyMonthly, tyMonthly, budgetMonthly, targetMonth }, totals = {}) {
    if (!tbody) return;
    tbody.innerHTML = "";

    let lySum = 0, tySum = 0, budSum = 0;

    MONTHS.forEach((label, i) => {
      const month = i + 1;
      const ly  = lyMonthly[i]     || 0;
      const ty  = tyMonthly[i]     || 0;
      const bud = budgetMonthly[i] || 0;

      lySum  += ly;
      tySum  += ty;
      budSum += bud;

      const isFuture  = month > targetMonth;
      const isCurrent = month === targetMonth;

      const yoy     = ly > 0 && !isFuture ? (ty - ly) / ly * 100 : null;
      const budRate = bud > 0 && !isFuture ? ty / bud * 100        : null;

      const tr = document.createElement("tr");
      if (isCurrent) tr.classList.add("detail-month-current");
      if (isFuture)  tr.classList.add("detail-month-future");

      const cell = (content, cls = "") =>
        `<td class="num${cls ? " " + cls : ""}">${content}</td>`;

      tr.innerHTML =
        `<td class="mth-label">${label}</td>` +
        cell(ly  > 0 ? fmt2.format(ly)  : "—") +
        cell(bud > 0 ? fmt2.format(bud) : "—") +
        cell(!isFuture ? (ty > 0 ? fmt2.format(ty) : "—") : "") +
        cell(!isFuture ? (budRate !== null ? budRate.toFixed(0) + "%" : "—") : "",
             _rateCls(budRate)) +
        cell(!isFuture ? (yoy !== null ? _signStr(yoy, 1) + "%" : "—") : "",
             _diffCls(yoy));

      tbody.appendChild(tr);
    });

    // Totals row
    const lyTotalYoy = lySum > 0 ? (tySum - lySum) / lySum * 100 : null;
    const budTotalRate = budSum > 0 ? tySum / budSum * 100 : null;

    _setCell(totals.lyTotalId,         lySum  > 0 ? fmt2.format(lySum)  : "—");
    _setCell(totals.budgetTotalId,     budSum > 0 ? fmt2.format(budSum) : "—");
    _setCell(totals.tyTotalId,         tySum  > 0 ? fmt2.format(tySum)  : "—");
    _setCell(totals.budgetRateTotalId, budTotalRate  !== null ? budTotalRate.toFixed(0) + "%"  : "—", _rateCls(budTotalRate));
    _setCell(totals.yoyTotalId,        lyTotalYoy !== null ? _signStr(lyTotalYoy, 1) + "%" : "—", _diffCls(lyTotalYoy));
  }


  // ── renderYtd ──────────────────────────────────────────────────────────────
  /**
   * Render the YTD cumulative comparison block.
   * @param {HTMLElement} container
   * @param {object} metrics       result of computeMetrics()
   * @param {number} targetMonth   1-based forecast month
   * @param {number} [lastActualMonth]  1-based last confirmed month (uses metrics.ytdCutoff as fallback)
   */
  function renderYtd(container, metrics, targetMonth, lastActualMonth) {
    if (!container) return;
    const { ytdLy, ytdTy, ytdBudget, ytdGapVsLy, ytdRateVsLy, ytdBudgetRate, ytdCutoff } = metrics;
    // 方向性比較（vs 去年）：台灣慣例 漲=rising(紅)、跌=falling(綠)
    const gapCls      = ytdGapVsLy   >= 0   ? "rising"   : "falling";
    // 100 = 與去年持平的基準，非達成率門檻
    const rateVsLyCls = ytdRateVsLy  >= 100 ? "rising"   : "falling";
    // 預算達成率四階 → fmt.js 唯一門檻（docs/adr/0004）
    const budRateCls  = ytdBudgetRate <= 0 ? "" : _rateCls(ytdBudgetRate);

    // Use the confirmed cutoff month for labels so user knows it's actual data
    const lbl = lastActualMonth || ytdCutoff || targetMonth;

    container.innerHTML = `
      <div class="ytd-grid">
        <div class="ytd-cell">
          <span class="ytd-label">去年 1–${lbl}月 實績</span>
          <span class="ytd-val">${ytdLy > 0 ? fmt0.format(ytdLy) : "—"}</span>
        </div>
        <div class="ytd-cell">
          <span class="ytd-label">預算 1–${lbl}月</span>
          <span class="ytd-val">${ytdBudget > 0 ? fmt0.format(ytdBudget) : "—"}</span>
        </div>
        <div class="ytd-cell">
          <span class="ytd-label">今年 1–${lbl}月 實績</span>
          <span class="ytd-val">${ytdTy > 0 ? fmt0.format(ytdTy) : "—"}</span>
        </div>
        <div class="ytd-cell">
          <span class="ytd-label">vs 去年差額</span>
          <span class="ytd-val ${gapCls}">${(ytdGapVsLy > 0 ? "+" : "") + fmt0.format(ytdGapVsLy)}</span>
        </div>
        <div class="ytd-cell">
          <span class="ytd-label">vs 去年</span>
          <span class="ytd-val ${rateVsLyCls}">${ytdLy > 0 ? ytdRateVsLy.toFixed(1) + "%" : "—"}</span>
        </div>
        <div class="ytd-cell">
          <span class="ytd-label">預算達成</span>
          <span class="ytd-val ${budRateCls}">${ytdBudget > 0 ? ytdBudgetRate.toFixed(1) + "%" : "—"}</span>
        </div>
      </div>`;
  }


  // ── renderAssessment ───────────────────────────────────────────────────────
  /**
   * Render moving average + trend direction block.
   * @param {HTMLElement} container
   * @param {object} metrics  result of computeMetrics()
   */
  function renderAssessment(container, metrics) {
    if (!container) return;
    const { ma3, ma6, trendDir } = metrics;
    const ARROWS = { up: "↑", flat: "→", down: "↓" };
    const LABELS = { up: "上升", flat: "持平", down: "下滑" };
    const CLASSES = { up: "rising", flat: "", down: "falling" };  // 台灣慣例：上升=紅、下滑=綠
    const arrow = ARROWS[trendDir] || "→";
    const label = LABELS[trendDir] || "持平";
    const cls   = CLASSES[trendDir] || "";

    container.innerHTML = `
      <div class="assess-row">
        <span>3MA（近3月均）</span>
        <span class="detail-val">${ma3 > 0 ? fmt2.format(ma3) : "—"}</span>
      </div>
      <div class="assess-row">
        <span>6MA（近6月均）</span>
        <span class="detail-val">${ma6 > 0 ? fmt2.format(ma6) : "—"}</span>
      </div>
      <div class="assess-row">
        <span>近期趨勢</span>
        <span class="detail-val ${cls}">${arrow} ${label}</span>
      </div>`;
  }


  // ── Private helpers ────────────────────────────────────────────────────────

  /**
   * Compute rolling MA as a 12-element array for this year's months.
   * Bridges last year + this year into a 24-month series so that even
   * January has a valid MA value (e.g. MA3 for Jan = avg(Oct, Nov, Dec LY)).
   * Returns null only for future months (i >= maxIndex).
   */
  function _rollingMA(lyMonthly, tyMonthly, period, maxIndex) {
    const combined = [...lyMonthly, ...tyMonthly];   // 24-month continuous series
    return tyMonthly.map((_, i) => {
      if (i >= maxIndex) return null;                 // future month
      const end   = i + 12;                          // this year month i maps to combined[i+12]
      const start = end - period + 1;
      const slice = combined.slice(start, end + 1);
      return slice.reduce((a, b) => a + b, 0) / period;
    });
  }

  function _sum(arr) {
    return (arr || []).reduce((a, b) => a + (b || 0), 0);
  }

  function _avg(arr) {
    const valid = (arr || []).filter(v => v > 0);
    return valid.length ? _sum(valid) / valid.length : 0;
  }

  // 格式化與語意 class 一律委派 fmt.js（唯一來源），這裡只留薄包裝。
  const _signStr = (n, decimals = 1) => fmt.signed(n, decimals);
  const _rateCls = (r) => fmt.rateCls(r);
  // YoY% 是方向性指標：台灣慣例 漲=rising(紅)、跌=falling(綠)
  const _diffCls = (r) => fmt.directionCls(r);

  function _setCell(id, text, cls = "") {
    if (!id) return;
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = text;
    if (cls !== undefined) el.className = cls;
  }

  // ── renderSparklineInCanvas ────────────────────────────────────────────────
  /**
   * Draw a compact sparkline for table rows (this year only, vs last year).
   * @param {HTMLCanvasElement} canvas
   * @param {number[]} lyMonthly      [12]
   * @param {number[]} tyMonthly      [12] confirmed actual only
   * @param {number}   targetMonth    1-based forecast month
   * @param {number}   [lastActualMonth]  1-based last confirmed month; defaults to targetMonth
   */
  function renderSparklineInCanvas(canvas, lyMonthly, tyMonthly, targetMonth, lastActualMonth) {
    const surface = setupCanvas(canvas, 80, 32);
    if (!surface) return;
    const { ctx, w, h } = surface;
    ctx.clearRect(0, 0, w, h);

    const pad = 2;
    const allVals = [...lyMonthly, ...tyMonthly].filter(v => v > 0);
    if (allVals.length === 0) return;
    const maxVal = Math.max(...allVals);
    const xOf = (i) => pad + (i / 11) * (w - pad * 2);
    const yOf = (v) => pad + (h - pad * 2) * (1 - v / maxVal);

    const actualCutoff = (lastActualMonth != null && lastActualMonth > 0)
      ? lastActualMonth : targetMonth;

    // Last year (gray, thin)
    _drawLine(ctx, lyMonthly, 12, xOf, yOf, COLOR_LY, 1);
    // This year (teal, up to lastActualMonth only — no 0-value gap for unconfirmed month)
    const tyMasked = tyMonthly.map((v, i) => (i < actualCutoff ? v : null));
    _drawLineMasked(ctx, tyMasked, xOf, yOf, COLOR_TY, 1.5);
  }


  // ── Public API ─────────────────────────────────────────────────────────────
  return {
    setupCanvas,
    computeMetrics,
    renderTrendChart,
    renderMonthlyTable,
    renderYtd,
    renderAssessment,
    renderSparklineInCanvas,
  };
})();

// Loaded as a plain <script> (no build step, ADR-0001); this guard is the node:test path.
if (typeof module !== "undefined" && module.exports) {
  module.exports = AnalyticsRenderer;
}
