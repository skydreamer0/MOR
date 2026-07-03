/**
 * fmt.js — semantic value formatting, defined once for all pages.
 *
 * 台灣慣例（方向性指標）：漲 = 紅 (.rising)、跌 = 綠 (.falling)
 * 達成語意（預算達成率）：達成 = 綠 (.positive)、未達 = 紅 (.negative)
 *
 * The class vocabulary (rising / falling / positive / negative) is the
 * interface between this module and mor.css. Jinja-side twin lives in
 * templates/_value_macros.html — keep thresholds in sync with it.
 *
 * Loaded as a plain <script> (no build step, per ADR-0001); the module.exports
 * guard exists only so node:test can import it.
 */

const AnalyticsFmt = (() => {
  "use strict";

  // 預算達成率門檻：>= ACHIEVED 算達成(綠)，< SHORTFALL 算明顯未達(紅)，中間不上色。
  const BUDGET_RATE_ACHIEVED = 100;
  const BUDGET_RATE_SHORTFALL = 80;

  const fmt0 = typeof Intl !== "undefined"
    ? new Intl.NumberFormat("zh-TW", { maximumFractionDigits: 0 })
    : { format: (n) => String(Math.round(n)) };

  /** Format a positive amount, em-dash for zero/absent. */
  function amount(v) {
    return v > 0 ? fmt0.format(v) : "—";
  }

  /** Escape a value for interpolation into innerHTML. */
  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  /**
   * YoY as signed delta percentage: (curr - prev) / prev.
   * 方向性指標 → rising / falling。prev 無資料時回傳 "—"。
   */
  function yoyDelta(curr, prev) {
    if (prev <= 0) return { text: "—", cls: "" };
    const pct = (curr - prev) / prev * 100;
    return {
      text: (pct > 0 ? "+" : "") + pct.toFixed(1) + "%",
      cls: pct > 0 ? "rising" : pct < 0 ? "falling" : "",
    };
  }

  /**
   * YoY as ratio percentage: curr / prev (100% = 持平).
   * 客戶/商品分析頁使用的表示法；同為方向性指標。
   */
  function yoyRatio(curr, prev) {
    if (prev <= 0) return { text: "—", cls: "" };
    const ratio = curr / prev * 100;
    return {
      text: ratio.toFixed(1) + "%",
      cls: ratio >= 100 ? "rising" : "falling",
    };
  }

  /** 預算達成率：達成語意 → positive / negative。 */
  function budgetRate(ty, budget) {
    if (budget <= 0) return { text: "—", cls: "" };
    const rate = ty / budget * 100;
    return {
      text: rate.toFixed(1) + "%",
      cls: rate >= BUDGET_RATE_ACHIEVED ? "positive"
         : rate < BUDGET_RATE_SHORTFALL ? "negative"
         : "",
    };
  }

  /**
   * Trend direction arrow ("up" | "flat" | "down").
   * withLabel=true renders "↑ 上升" style, otherwise arrow only.
   * 上升=紅、下滑=綠（台灣慣例）。
   */
  function trendArrow(dir, withLabel = false) {
    const ARROWS = { up: "↑", flat: "→", down: "↓" };
    const LABELS = { up: "上升", flat: "持平", down: "下滑" };
    const CLASSES = { up: "rising", flat: "", down: "falling" };
    const arrow = ARROWS[dir] || "→";
    return {
      text: withLabel ? `${arrow} ${LABELS[dir] || "持平"}` : arrow,
      cls: CLASSES[dir] || "",
    };
  }

  return {
    amount,
    escapeHtml,
    yoyDelta,
    yoyRatio,
    budgetRate,
    trendArrow,
    BUDGET_RATE_ACHIEVED,
    BUDGET_RATE_SHORTFALL,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = AnalyticsFmt;
}
