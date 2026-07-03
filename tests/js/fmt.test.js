"use strict";
// node --test tests/js/  (wrapped by tests/test_frontend_js.py)
const { test } = require("node:test");
const assert = require("node:assert/strict");

const fmt = require("../../static/js/fmt.js");

test("yoyDelta: signed delta with Taiwan direction classes", () => {
  assert.deepEqual(fmt.yoyDelta(110, 100), { text: "+10.0%", cls: "rising" });
  assert.deepEqual(fmt.yoyDelta(90, 100), { text: "-10.0%", cls: "falling" });
  assert.deepEqual(fmt.yoyDelta(100, 100), { text: "0.0%", cls: "" });
  assert.deepEqual(fmt.yoyDelta(50, 0), { text: "—", cls: "" });
});

test("yoyRatio: ratio percentage, 100% boundary counts as rising", () => {
  assert.deepEqual(fmt.yoyRatio(95, 100), { text: "95.0%", cls: "falling" });
  assert.deepEqual(fmt.yoyRatio(100, 100), { text: "100.0%", cls: "rising" });
  assert.deepEqual(fmt.yoyRatio(120, 100), { text: "120.0%", cls: "rising" });
  assert.deepEqual(fmt.yoyRatio(50, 0), { text: "—", cls: "" });
});

test("budgetRate: achievement semantics with 100/80 thresholds", () => {
  assert.deepEqual(fmt.budgetRate(100, 100), { text: "100.0%", cls: "positive" });
  assert.deepEqual(fmt.budgetRate(79, 100), { text: "79.0%", cls: "negative" });
  assert.deepEqual(fmt.budgetRate(80, 100), { text: "80.0%", cls: "" });
  assert.deepEqual(fmt.budgetRate(99, 100), { text: "99.0%", cls: "" });
  assert.deepEqual(fmt.budgetRate(50, 0), { text: "—", cls: "" });
});

test("trendArrow: icon and labelled variants", () => {
  assert.deepEqual(fmt.trendArrow("up"), { text: "↑", cls: "rising" });
  assert.deepEqual(fmt.trendArrow("down"), { text: "↓", cls: "falling" });
  assert.deepEqual(fmt.trendArrow("flat"), { text: "→", cls: "" });
  assert.deepEqual(fmt.trendArrow("up", true), { text: "↑ 上升", cls: "rising" });
  assert.deepEqual(fmt.trendArrow("down", true), { text: "↓ 下滑", cls: "falling" });
  assert.deepEqual(fmt.trendArrow(undefined), { text: "→", cls: "" });
});

test("amount: grouped digits, em-dash for zero or negative", () => {
  assert.equal(fmt.amount(1234567), "1,234,567");
  assert.equal(fmt.amount(0), "—");
  assert.equal(fmt.amount(-5), "—");
});

test("escapeHtml: neutralises markup and quotes", () => {
  assert.equal(
    fmt.escapeHtml(`<img src=x onerror="pwn()">'&`),
    "&lt;img src=x onerror=&quot;pwn()&quot;&gt;&#39;&amp;"
  );
  assert.equal(fmt.escapeHtml(null), "");
  assert.equal(fmt.escapeHtml(undefined), "");
});
