"use strict";
// node --test tests/js/  (wrapped by tests/test_frontend_js.py)
const { test } = require("node:test");
const assert = require("node:assert/strict");

const MonitorTable = require("../../static/js/monitor-table.js");

function makeCell(text) {
  return { textContent: text };
}

function makeRow(label, values) {
  const row = {
    label,
    hidden: false,
    dataset: {},
    cells: values.map(makeCell),
    detail: { label: `${label}-detail` },
    nextElementSibling: null,
  };
  row.nextElementSibling = row.detail;
  row.detail.hasAttribute = (name) => name === "data-monitor-detail";
  return row;
}

function makeExpandableRow() {
  const attrs = { "aria-expanded": "false" };
  const detail = {
    hidden: true,
    hasAttribute(name) {
      return name === "data-monitor-detail";
    },
  };
  return {
    nextElementSibling: detail,
    getAttribute(name) {
      return attrs[name];
    },
    setAttribute(name, value) {
      attrs[name] = value;
    },
  };
}

test("sortRows keeps monitor detail rows paired with their main rows", () => {
  const alpha = makeRow("alpha", ["注意", "A Clinic", "針劑", "05/02", "8天", "7"]);
  const beta = makeRow("beta", ["高風險", "B Hospital", "藥品", "05/01", "12天", "3"]);
  const tbody = {
    appended: [],
    appendChild(node) {
      this.appended.push(node);
    },
  };

  MonitorTable.sortRows(tbody, [alpha, beta], { column: 5, type: "number", direction: "asc" });

  assert.deepEqual(tbody.appended.map((node) => node.label), [
    "beta",
    "beta-detail",
    "alpha",
    "alpha-detail",
  ]);
});

test("toggleMonitorRow toggles aria-expanded and the paired detail row", () => {
  const row = makeExpandableRow();

  MonitorTable.toggleMonitorRow(row);

  assert.equal(row.getAttribute("aria-expanded"), "true");
  assert.equal(row.nextElementSibling.hidden, false);

  MonitorTable.toggleMonitorRow(row);

  assert.equal(row.getAttribute("aria-expanded"), "false");
  assert.equal(row.nextElementSibling.hidden, true);
});

test("sortRows puts hidden filtered rows after visible rows", () => {
  const hidden = makeRow("hidden", ["注意", "A Clinic"]);
  const visible = makeRow("visible", ["正常", "B Hospital"]);
  hidden.hidden = true;
  const tbody = {
    appended: [],
    appendChild(node) {
      this.appended.push(node);
    },
  };

  MonitorTable.sortRows(tbody, [hidden, visible], { column: 1, type: "text", direction: "asc" });

  assert.deepEqual(tbody.appended.map((node) => node.label), [
    "visible",
    "visible-detail",
    "hidden",
    "hidden-detail",
  ]);
});

test("sortRows captures detail pairs before moving DOM nodes", () => {
  const alpha = makeRow("alpha", ["注意", "A Clinic"]);
  const beta = makeRow("beta", ["高風險", "B Hospital"]);
  const tbody = {
    appended: [],
    appendChild(node) {
      this.appended.push(node);
      if (!node.hasAttribute) node.nextElementSibling = null;
    },
  };

  MonitorTable.sortRows(tbody, [alpha, beta], { column: 1, type: "text", direction: "desc" });

  assert.deepEqual(tbody.appended.map((node) => node.label), [
    "beta",
    "beta-detail",
    "alpha",
    "alpha-detail",
  ]);
});
