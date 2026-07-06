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
