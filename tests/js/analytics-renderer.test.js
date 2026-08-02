"use strict";
// node --test tests/js/  (wrapped by tests/test_frontend_js.py)
const { test } = require("node:test");
const assert = require("node:assert/strict");

const AnalyticsRenderer = require("../../static/js/analytics-renderer.js");

// setupCanvas itself moved to canvas.js in FE-14 — see tests/js/canvas.test.js.

test("renderTrendChart and renderSparklineInCanvas tolerate a missing canvas", () => {
  assert.doesNotThrow(() => AnalyticsRenderer.renderTrendChart(null, {
    lyMonthly: [], tyMonthly: [], budgetMonthly: [], targetMonth: 1,
  }));
  assert.doesNotThrow(() => AnalyticsRenderer.renderSparklineInCanvas(null, [], [], 1));
});
