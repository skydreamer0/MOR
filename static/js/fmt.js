/**
 * fmt.js — semantic value formatting, defined once for all pages.
 *
 * 台灣慣例（方向性指標）：漲 = 紅 (.rising)、跌 = 綠 (.falling)
 * 達成語意（預算達成率四階，正典詞彙見 docs/adr/0004）：
 *   >=100 .positive(綠) / 90-99 .warning(橙) / 80-89 .caution(棕) / <80 .negative(紅)
 *
 * This module is the single formatting source for the whole frontend:
 * forecast-table.js、analytics-table.js、analytics-renderer.js 全部委派這裡，
 * 門檻常數只有 BUDGET_RATE_* 這一份。Jinja-side twin lives in
 * templates/_value_macros.html — keep thresholds in sync with it.
 *
 * Loaded as a plain <script> (no build step, per ADR-0001); the module.exports
 * guard exists only so node:test can import it.
 */

const AnalyticsFmt = (() => {
  "use strict";

  // 預算達成率四階門檻：>=ACHIEVED 達成(綠)，>=WARNING 警戒(橙)，>=CAUTION 注意(棕)，< CAUTION 明顯未達(紅)。
  const BUDGET_RATE_ACHIEVED = 100;
  const BUDGET_RATE_WARNING = 90;
  const BUDGET_RATE_CAUTION = 80;

  const fmt0 = typeof Intl !== "undefined"
    ? new Intl.NumberFormat("zh-TW", { maximumFractionDigits: 0 })
    : { format: (n) => String(Math.round(n)) };

  /** Format a positive amount, em-dash for zero/absent. */
  function amount(v) {
    return v > 0 ? fmt0.format(v) : "—";
  }

  /** Format any number with thousands separators, no decimals (0 stays "0"). */
  function number(v) {
    return fmt0.format(v);
  }

  /** Thousands-separated integer with an explicit "+" for positives. */
  function signedNumber(v) {
    return (v > 0 ? "+" : "") + fmt0.format(v);
  }

  /** Fixed-decimal number with an explicit "+" for positives (no grouping). */
  function signed(v, decimals = 1) {
    return (v > 0 ? "+" : "") + v.toFixed(decimals);
  }

  /** Percentage text from an already-computed rate (e.g. 93.4 → "93.4%"). */
  function percent(v, decimals = 1) {
    return v.toFixed(decimals) + "%";
  }

  /**
   * 達成率四階 class（正典詞彙，見 docs/adr/0004）。
   * 輸入已算好的百分比；null/undefined 回傳 ""。
   */
  function rateCls(rate) {
    if (rate === null || rate === undefined || Number.isNaN(rate)) return "";
    return rate >= BUDGET_RATE_ACHIEVED ? "positive"
         : rate >= BUDGET_RATE_WARNING  ? "warning"
         : rate >= BUDGET_RATE_CAUTION  ? "caution"
         : "negative";
  }

  /** 方向性指標 class：台灣慣例 漲=rising(紅)、跌=falling(綠)。 */
  function directionCls(v) {
    if (v === null || v === undefined || Number.isNaN(v)) return "";
    return v > 0 ? "rising" : v < 0 ? "falling" : "";
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
      text: signed(pct) + "%",
      cls: directionCls(pct),
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
      text: percent(ratio),
      // 這裡的 100 是「持平」基準（curr == prev），與達成率門檻無關，故不引用 BUDGET_RATE_*。
      cls: ratio >= 100 ? "rising" : "falling",
    };
  }

  /** 預算達成率：達成語意四階 → positive / warning / caution / negative。 */
  function budgetRate(ty, budget) {
    if (budget <= 0) return { text: "—", cls: "" };
    const rate = ty / budget * 100;
    return { text: percent(rate), cls: rateCls(rate) };
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
    number,
    signed,
    signedNumber,
    percent,
    escapeHtml,
    yoyDelta,
    yoyRatio,
    budgetRate,
    rateCls,
    directionCls,
    trendArrow,
    BUDGET_RATE_ACHIEVED,
    BUDGET_RATE_WARNING,
    BUDGET_RATE_CAUTION,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = AnalyticsFmt;
}
