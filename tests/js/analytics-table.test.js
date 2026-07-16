"use strict";
// node --test tests/js/  (wrapped by tests/test_frontend_js.py)
const { test } = require("node:test");
const assert = require("node:assert/strict");

const AnalyticsTable = require("../../static/js/analytics-table.js");

const METRICS = { ytdLy: 1000, ytdTy: 1100, ytdBudget: 1200, trendDir: "up" };
const QTY_METRICS = { ytdLy: 50, ytdTy: 40 };
const SLICE = { entity_label: "台大醫院", entity_id: "C001" };

const DASH_OPTS = {
  targetMonth: 7,
  idPrefix: "customer",
  columns: ["lyAmount", "budgetAmount", "tyAmount", "budgetRate", "yoyDelta", "trendIcon", "spark"],
  labelClass: "dash-entity-label",
  sparkClass: "dash-spark-canvas",
};

test("buildRowCells: renders label + one cell per column", () => {
  const html = AnalyticsTable.buildRowCells(SLICE, METRICS, null, "spark-customer-0", DASH_OPTS);
  const cellCount = (html.match(/<td/g) || []).length;
  assert.equal(cellCount, DASH_OPTS.columns.length + 1);
  assert.ok(html.includes('class="dash-entity-label"'));
  assert.ok(html.includes("1,000"));   // lyAmount
  assert.ok(html.includes("1,200"));   // budgetAmount
  assert.ok(html.includes("+10.0%"));  // yoyDelta 1100 vs 1000
  assert.ok(html.includes("rising"));  // trend up
  assert.ok(html.includes('id="spark-customer-0"'));
});

test("buildRowCells: escapes hostile entity labels and ids", () => {
  const hostile = {
    entity_label: '<script>alert(1)</script>',
    entity_id: '"><img src=x>',
  };
  const html = AnalyticsTable.buildRowCells(
    hostile, METRICS, null, "spark-x-0",
    { ...DASH_OPTS, boldLabel: true, showEntityId: true }
  );
  assert.ok(!html.includes("<script>"));
  assert.ok(!html.includes("<img"));
  assert.ok(html.includes("&lt;script&gt;"));
});

test("buildRowCells: yoyQtyDelta reads quantity metrics", () => {
  const html = AnalyticsTable.buildRowCells(
    SLICE, METRICS, QTY_METRICS, "spark-product-0",
    { ...DASH_OPTS, columns: ["yoyDelta", "yoyQtyDelta"] }
  );
  assert.ok(html.includes("+10.0%"));  // amount 1100/1000
  assert.ok(html.includes("-20.0%")); // qty 40/50
});

test("buildRowCells: management analytics uses signed YoY delta", () => {
  const html = AnalyticsTable.buildRowCells(
    SLICE, METRICS, QTY_METRICS, "spark-management-0",
    { ...DASH_OPTS, columns: ["yoyDelta", "trendLabel"] }
  );
  assert.ok(html.includes("+10.0%"));
  assert.ok(!html.includes("110.0%"));
});

test("buildRowCells: unknown column throws", () => {
  assert.throws(
    () => AnalyticsTable.buildRowCells(SLICE, METRICS, null, "c0", { ...DASH_OPTS, columns: ["nope"] }),
    /unknown column/
  );
});

test("buildDetailHtml: colspan and idPrefix-scoped element ids", () => {
  const html = AnalyticsTable.buildDetailHtml(3, 8, { idPrefix: "cust" });
  assert.ok(html.includes('colspan="8"'));
  assert.ok(html.includes('id="cust-chart-3"'));
  assert.ok(html.includes('id="cust-ytd-3"'));
  assert.ok(html.includes('id="cust-assess-3"'));
  assert.ok(html.includes('id="cust-monthly-3"'));
});
