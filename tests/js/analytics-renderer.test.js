"use strict";
// node --test tests/js/  (wrapped by tests/test_frontend_js.py)
const { test } = require("node:test");
const assert = require("node:assert/strict");

const AnalyticsRenderer = require("../../static/js/analytics-renderer.js");

/* ── FE-14: shared HiDPI canvas setup ───────────────────────────────── */

function makeCanvas(clientWidth, clientHeight) {
  const calls = [];
  return {
    clientWidth,
    clientHeight,
    width: 0,
    height: 0,
    calls,
    getContext() {
      return { scale: (x, y) => calls.push(["scale", x, y]) };
    },
  };
}

function withDpr(dpr, fn) {
  const had = "window" in globalThis;
  const previous = globalThis.window;
  globalThis.window = { devicePixelRatio: dpr };
  try {
    return fn();
  } finally {
    if (had) globalThis.window = previous;
    else delete globalThis.window;
  }
}

test("setupCanvas sizes the backing store by devicePixelRatio and pre-scales the context", () => {
  const canvas = makeCanvas(340, 110);

  const surface = withDpr(2, () => AnalyticsRenderer.setupCanvas(canvas, 340, 110));

  assert.equal(canvas.width, 680);
  assert.equal(canvas.height, 220);
  // Callers keep drawing in CSS pixels, so w/h are the unscaled values.
  assert.equal(surface.w, 340);
  assert.equal(surface.h, 110);
  assert.deepEqual(canvas.calls, [["scale", 2, 2]]);
});

test("setupCanvas leaves dimensions untouched at devicePixelRatio 1", () => {
  const canvas = makeCanvas(80, 24);

  const surface = withDpr(1, () => AnalyticsRenderer.setupCanvas(canvas, 80, 24));

  assert.equal(canvas.width, 80);
  assert.equal(canvas.height, 24);
  assert.equal(surface.w, 80);
  assert.equal(surface.h, 24);
});

test("setupCanvas falls back to the per-call-site dimensions when the canvas is not laid out", () => {
  // A canvas inside a hidden ancestor reports clientWidth/clientHeight 0.
  const trend    = makeCanvas(0, 0);
  const sparkRow = makeCanvas(0, 0);
  const forecast = makeCanvas(0, 0);

  withDpr(1, () => {
    // The three call sites deliberately keep different fallbacks.
    AnalyticsRenderer.setupCanvas(trend, 340, 110);     // renderTrendChart
    AnalyticsRenderer.setupCanvas(sparkRow, 80, 32);    // renderSparklineInCanvas
    AnalyticsRenderer.setupCanvas(forecast, 80, 24);    // forecast-table drawSparkline
  });

  assert.deepEqual([trend.width, trend.height], [340, 110]);
  assert.deepEqual([sparkRow.width, sparkRow.height], [80, 32]);
  assert.deepEqual([forecast.width, forecast.height], [80, 24]);
});

test("setupCanvas returns null for a missing canvas so callers can bail out", () => {
  assert.equal(AnalyticsRenderer.setupCanvas(null, 80, 24), null);
  assert.equal(AnalyticsRenderer.setupCanvas(undefined, 80, 24), null);
});

test("renderTrendChart and renderSparklineInCanvas tolerate a missing canvas", () => {
  assert.doesNotThrow(() => AnalyticsRenderer.renderTrendChart(null, {
    lyMonthly: [], tyMonthly: [], budgetMonthly: [], targetMonth: 1,
  }));
  assert.doesNotThrow(() => AnalyticsRenderer.renderSparklineInCanvas(null, [], [], 1));
});
