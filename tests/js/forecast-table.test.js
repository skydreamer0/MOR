"use strict";
// node --test tests/js/  (wrapped by tests/test_frontend_js.py)
const { test } = require("node:test");
const assert = require("node:assert/strict");

const ForecastTable = require("../../static/js/forecast-table.js");

function makeInput(value) {
  return {
    value,
    setAttribute() {},
  };
}

function makeRow(statePayload, manualValue = "", reasonValue = "") {
  const manual = makeInput(manualValue);
  const reason = makeInput(reasonValue);
  return {
    dataset: {
      rowId: "A__P1",
      status: "auto",
      search: "Hospital Product",
      state: JSON.stringify(statePayload),
    },
    querySelector(selector) {
      if (selector === "[data-manual]") return manual;
      if (selector === "[data-reason]") return reason;
      return null;
    },
  };
}

test("readRowState reads calculation fields from data-state JSON", () => {
  const row = makeRow({
    price: 250,
    price_quantity: 10,
    system_forecast: 12,
    actual_quantity: 3,
    budget_quantity: 8,
    lm_actual: 5,
    lm_budget: 4,
    excluded: false,
  }, "14", "reviewed");

  const state = ForecastTable.readRowState(row);

  assert.equal(state.rowId, "A__P1");
  assert.equal(state.price, 250);
  assert.equal(state.priceQuantity, 10);
  assert.equal(state.systemForecast, 12);
  assert.equal(state.actualQuantity, 3);
  assert.equal(state.budgetQuantity, 8);
  assert.equal(state.lmActual, 5);
  assert.equal(state.lmBudget, 4);
  assert.equal(state.manualValue, "14");
  assert.equal(state.reason, "reviewed");
  assert.equal(state.excluded, false);
});

test("calculateAmount uses packed price quantity and excludes unbudgeted rows", () => {
  const included = ForecastTable.readRowState(makeRow({
    price: 250,
    price_quantity: 10,
    system_forecast: 12,
    budget_quantity: 8,
    excluded: false,
  }, ""));
  const unbudgeted = ForecastTable.readRowState(makeRow({
    price: 250,
    price_quantity: 10,
    system_forecast: 12,
    budget_quantity: 0,
    excluded: false,
  }, ""));

  assert.equal(ForecastTable.calculateAmount(included), 300);
  assert.equal(ForecastTable.calculateAmount(unbudgeted), 0);
});

/* ── FE-8: 達成率四階門檻（正典 class 詞彙，見 docs/adr/0004） ───────── */

function makeRateEl() {
  const classes = new Set();
  return {
    textContent: "",
    classes,
    classList: {
      toggle(name, on) {
        if (on) classes.add(name); else classes.delete(name);
      },
    },
  };
}

function rateClassOf(value) {
  const el = makeRateEl();
  ForecastTable.updateRateElement(el, value);
  return { cls: [...el.classes], text: el.textContent };
}

test("updateRateElement applies all four achievement tiers at their boundaries", () => {
  assert.deepEqual(rateClassOf(100).cls, ["positive"]);
  assert.deepEqual(rateClassOf(99).cls,  ["warning"]);
  assert.deepEqual(rateClassOf(90).cls,  ["warning"]);
  assert.deepEqual(rateClassOf(89).cls,  ["caution"]);
  assert.deepEqual(rateClassOf(80).cls,  ["caution"]);
  assert.deepEqual(rateClassOf(79).cls,  ["negative"]);
  assert.deepEqual(rateClassOf(0).cls,   ["negative"]);
});

test("updateRateElement formats the rate to one decimal with a percent sign", () => {
  assert.equal(rateClassOf(93.45).text, "93.5%");
  assert.equal(rateClassOf(100).text, "100.0%");
});

test("updateRateElement replaces the previous tier class instead of stacking", () => {
  const el = makeRateEl();
  ForecastTable.updateRateElement(el, 105);
  assert.deepEqual([...el.classes], ["positive"]);
  ForecastTable.updateRateElement(el, 70);
  assert.deepEqual([...el.classes], ["negative"]);
});

test("updateRateElement tolerates a missing element", () => {
  assert.doesNotThrow(() => ForecastTable.updateRateElement(null, 50));
});
