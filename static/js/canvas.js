/**
 * canvas.js — HiDPI canvas boilerplate, shared by every canvas painter.
 *
 * Extracted in FE-14. The `devicePixelRatio` → size the backing store →
 * `ctx.scale` dance was repeated in four places; three of them could share via
 * analytics-renderer.js, but gap-sparkline.js runs on Product Monitor, which
 * (since FE-13) does not load the analytics bundle at all. Rather than pull
 * 490 lines of renderer into that page for one helper, the helper lives here.
 *
 * Deliberately dependency-free and tiny — any page with a canvas can load it.
 *
 * Loaded as a plain <script> (no build step, per ADR-0001); the module.exports
 * guard exists only so node:test can import it.
 */

const MorCanvas = (() => {
  "use strict";

  /**
   * Size a canvas for the current devicePixelRatio and return a context that
   * is pre-scaled, so all drawing code can keep working in CSS pixels.
   *
   * Width/height come from `clientWidth`/`clientHeight`. The fallbacks are
   * per call site because each canvas has its own intrinsic size, and they are
   * only reached when the element is not laid out yet (e.g. hidden ancestor,
   * where clientWidth is 0).
   *
   * gap-sparkline.js previously read `offsetWidth`/`offsetHeight` here. Its
   * canvas (`.gap-sparkline`) has no border or padding, so the two are equal;
   * unified on the client* pair to keep one code path.
   *
   * Note: assigning `canvas.width` already clears the surface. Call sites that
   * additionally call `clearRect` keep doing so — it is a harmless no-op.
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

  return { setupCanvas };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = MorCanvas;
}
