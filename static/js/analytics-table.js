/**
 * analytics-table.js — the single table controller for analytics slices.
 *
 * Replaces the three near-identical inline controllers that lived in
 * customers.html, products.html and _dashboard_metrics.html. Pages call:
 *
 *   AnalyticsTable.mount(tbody, slices, {
 *     targetMonth: 7,
 *     idPrefix: "cust",
 *     columns: ["lyAmount","budgetAmount","tyAmount","budgetRate","yoyDelta","trendLabel","spark"],
 *     boldLabel: true,
 *     expandable: true,          // click/Enter toggles the detail row
 *     sparkSeries: "amount",     // "amount" | "qty"
 *   });
 *
 * Column vocabulary (order = render order; "label" is always first):
 *   lyAmount / budgetAmount / tyAmount  — YTD amounts
 *   budgetRate                          — 預算達成 (positive/warning/caution/negative)
 *   yoyDelta                            — YoY as signed delta, amount-based
 *   yoyQtyDelta                         — YoY as signed delta, quantity-based
 *   yoyRatio                            — legacy ratio display; do not use for management analytics
 *   trendIcon / trendLabel              — 趨勢 arrow, with/without 上升/下滑 text
 *   spark                               — 12-month sparkline canvas
 *
 * Semantic colouring is delegated to AnalyticsFmt (fmt.js); charting to
 * AnalyticsRenderer. Entity labels are HTML-escaped here — slices are data,
 * never markup. buildRowCells() is pure so node:test can cover it without a DOM.
 */

const AnalyticsTable = (() => {
  "use strict";

  const fmt = typeof AnalyticsFmt !== "undefined" ? AnalyticsFmt : require("./fmt.js");

  function _numCell({ text, cls }) {
    return `<td class="num${cls ? " " + cls : ""}">${text}</td>`;
  }

  function _labelCell(slice, opts) {
    const label = fmt.escapeHtml(slice.entity_label);
    const cls = opts.labelClass ? ` class="${opts.labelClass}"` : "";
    const name = opts.boldLabel ? `<strong>${label}</strong>` : label;
    const sub = opts.showEntityId
      ? `<br><span style="color:var(--text-secondary);font-size:var(--text-sm)">${fmt.escapeHtml(slice.entity_id)}</span>`
      : "";
    return `<td${cls}>${name}${sub}</td>`;
  }

  function _sparkCell(canvasId, opts) {
    const canvas = opts.sparkClass
      ? `<canvas id="${canvasId}" class="${opts.sparkClass}" aria-hidden="true"></canvas>`
      : `<canvas id="${canvasId}" width="80" height="32" style="display:block;" aria-hidden="true"></canvas>`;
    return `<td>${canvas}</td>`;
  }

  /**
   * Build the <td> sequence for one summary row. Pure — no DOM access.
   * @returns {string} innerHTML for the <tr>
   */
  function buildRowCells(slice, amtM, qtyM, canvasId, opts) {
    const cells = [_labelCell(slice, opts)];

    for (const col of opts.columns) {
      switch (col) {
        case "lyAmount":
          cells.push(_numCell({ text: fmt.amount(amtM.ytdLy), cls: "" }));
          break;
        case "budgetAmount":
          cells.push(_numCell({ text: fmt.amount(amtM.ytdBudget), cls: "" }));
          break;
        case "tyAmount":
          cells.push(_numCell({ text: fmt.amount(amtM.ytdTy), cls: "" }));
          break;
        case "budgetRate":
          cells.push(_numCell(fmt.budgetRate(amtM.ytdTy, amtM.ytdBudget)));
          break;
        case "yoyDelta":
          cells.push(_numCell(fmt.yoyDelta(amtM.ytdTy, amtM.ytdLy)));
          break;
        case "yoyQtyDelta":
          cells.push(_numCell(fmt.yoyDelta(qtyM.ytdTy, qtyM.ytdLy)));
          break;
        case "yoyRatio":
          cells.push(_numCell(fmt.yoyRatio(amtM.ytdTy, amtM.ytdLy)));
          break;
        case "trendIcon":
          cells.push(_numCell(fmt.trendArrow(amtM.trendDir, false)));
          break;
        case "trendLabel":
          cells.push(_numCell(fmt.trendArrow(amtM.trendDir, true)));
          break;
        case "spark":
          cells.push(_sparkCell(canvasId, opts));
          break;
        default:
          throw new Error(`AnalyticsTable: unknown column "${col}"`);
      }
    }
    return cells.join("");
  }

  function _sparkData(slice, opts) {
    return opts.sparkSeries === "qty"
      ? [slice.ly_monthly, slice.ty_monthly]
      : [slice.ly_monthly_amount, slice.ty_monthly_amount];
  }

  /** Detail row markup for expandable tables (customers/products pages). */
  function buildDetailHtml(idx, colspan, opts) {
    const p = opts.idPrefix;
    return `<td colspan="${colspan}">
      <div style="padding:var(--sp-4);background:var(--surface);border-radius:var(--radius);">
        <div style="display:grid;grid-template-columns:1fr 280px;gap:var(--sp-5);margin-bottom:var(--sp-4);">
          <div>
            <canvas id="${p}-chart-${idx}" style="width:100%;height:120px;display:block;" aria-hidden="true"></canvas>
            <div class="detail-chart-legend" style="margin-top:var(--sp-2);">
              <span class="legend-ly">去年</span>
              <span class="legend-budget">預算</span>
              <span class="legend-ty">今年</span>
            </div>
          </div>
          <div>
            <div id="${p}-ytd-${idx}"></div>
            <div id="${p}-assess-${idx}" style="margin-top:var(--sp-3);"></div>
          </div>
        </div>
        <table class="dash-analytics-table management-table" style="font-size:var(--text-sm);">
          <thead>
            <tr>
              <th>月</th>
              <th class="num">去年金額</th>
              <th class="num">預算金額</th>
              <th class="num">今年金額</th>
              <th class="num">達成%</th>
              <th class="num">YoY%</th>
            </tr>
          </thead>
          <tbody id="${p}-monthly-${idx}"></tbody>
        </table>
      </div>
    </td>`;
  }

  function _renderDetail(slice, metrics, idx, opts) {
    const p = opts.idPrefix;
    const fcstMonthly = new Array(12).fill(0);
    fcstMonthly[opts.targetMonth - 1] = slice.forecast_amount || 0;

    AnalyticsRenderer.renderTrendChart(document.getElementById(`${p}-chart-${idx}`), {
      lyMonthly:       slice.ly_monthly_amount,
      tyMonthly:       slice.ty_monthly_amount,
      budgetMonthly:   slice.budget_monthly_amount,
      forecastMonthly: fcstMonthly,
      targetMonth:     opts.targetMonth,
      lastActualMonth: slice.last_actual_month,
    });
    AnalyticsRenderer.renderYtd(
      document.getElementById(`${p}-ytd-${idx}`), metrics, opts.targetMonth, slice.last_actual_month
    );
    AnalyticsRenderer.renderAssessment(
      document.getElementById(`${p}-assess-${idx}`), metrics
    );
    AnalyticsRenderer.renderMonthlyTable(
      document.getElementById(`${p}-monthly-${idx}`), {
        lyMonthly:     slice.ly_monthly_amount,
        tyMonthly:     slice.ty_monthly_amount,
        budgetMonthly: slice.budget_monthly_amount,
        targetMonth:   opts.targetMonth,
      }
    );
  }

  function _attachDetail(tbody, tr, slice, metrics, idx, opts) {
    const detail = document.createElement("tr");
    detail.style.display = "none";
    detail.innerHTML = buildDetailHtml(idx, opts.columns.length + 1, opts);
    tbody.appendChild(detail);

    tr.style.cursor = "pointer";
    tr.title = "點擊展開月別明細";
    tr.tabIndex = 0;
    tr.setAttribute("aria-expanded", "false");

    const toggle = () => {
      const isOpen = detail.style.display !== "none";
      detail.style.display = isOpen ? "none" : "";
      tr.setAttribute("aria-expanded", String(!isOpen));
      if (!isOpen) _renderDetail(slice, metrics, idx, opts);
    };
    tr.addEventListener("click", toggle);
    tr.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        toggle();
      }
    });
  }

  /**
   * Render all slices into tbody. See module docstring for options.
   */
  function mount(tbody, slices, opts) {
    if (!tbody || !slices || !slices.length) return;
    const needQty = opts.columns.includes("yoyQtyDelta");

    slices.forEach((slice, idx) => {
      const amtM = AnalyticsRenderer.computeMetrics(
        slice.ly_monthly_amount, slice.ty_monthly_amount, slice.budget_monthly_amount,
        opts.targetMonth, slice.last_actual_month
      );
      const qtyM = needQty
        ? AnalyticsRenderer.computeMetrics(
            slice.ly_monthly, slice.ty_monthly, slice.budget_monthly,
            opts.targetMonth, slice.last_actual_month
          )
        : null;

      const canvasId = `spark-${opts.idPrefix}-${idx}`;
      const tr = document.createElement("tr");
      tr.innerHTML = buildRowCells(slice, amtM, qtyM, canvasId, opts);
      tbody.appendChild(tr);

      if (opts.columns.includes("spark")) {
        const [ly, ty] = _sparkData(slice, opts);
        requestAnimationFrame(() => {
          AnalyticsRenderer.renderSparklineInCanvas(
            document.getElementById(canvasId), ly, ty, opts.targetMonth, slice.last_actual_month
          );
        });
      }

      if (opts.expandable) {
        _attachDetail(tbody, tr, slice, amtM, idx, opts);
      }
    });
  }

  return { mount, buildRowCells, buildDetailHtml };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = AnalyticsTable;
}
