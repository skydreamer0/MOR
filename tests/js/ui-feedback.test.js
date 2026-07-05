"use strict";
// node --test tests/js/  (wrapped by tests/test_frontend_js.py)
const { test, beforeEach } = require("node:test");
const assert = require("node:assert/strict");

class FakeEventTarget {
  constructor() {
    this.listeners = {};
  }

  addEventListener(type, handler) {
    this.listeners[type] = this.listeners[type] || [];
    this.listeners[type].push(handler);
  }

  dispatch(type, event) {
    for (const handler of this.listeners[type] || []) {
      handler(event);
    }
  }
}

class FakeClassList {
  constructor() {
    this.values = new Set();
  }

  add(value) {
    this.values.add(value);
  }

  contains(value) {
    return this.values.has(value);
  }
}

class FakeButton {
  constructor() {
    this.classList = new FakeClassList();
    this.disabled = false;
  }
}

class FakeForm {
  constructor({ confirmMessage, button } = {}) {
    this.dataset = {};
    if (confirmMessage) this.dataset.confirm = confirmMessage;
    this.button = button || null;
    this.requestSubmitCount = 0;
  }

  querySelector(selector) {
    if (selector === 'button[type="submit"], button:not([type])') return this.button;
    return null;
  }

  requestSubmit() {
    this.requestSubmitCount += 1;
  }
}

function submitEvent(form) {
  return {
    target: form,
    defaultPrevented: false,
    immediateStopped: false,
    preventDefault() { this.defaultPrevented = true; },
    stopImmediatePropagation() { this.immediateStopped = true; },
  };
}

beforeEach(() => {
  delete require.cache[require.resolve("../../static/js/ui-feedback.js")];
});

test("appConfirm falls back to native confirm when dialog is unavailable", async () => {
  const document = new FakeEventTarget();
  document.getElementById = () => null;
  global.document = document;
  global.window = { confirm: () => true };
  global.HTMLFormElement = FakeForm;

  require("../../static/js/ui-feedback.js");

  assert.equal(await window.appConfirm({ message: "確定？" }), true);
});

test("data-confirm submit uses appConfirm before requestSubmit", async () => {
  const document = new FakeEventTarget();
  document.getElementById = () => null;
  global.document = document;
  global.window = { confirm: () => true };
  global.HTMLFormElement = FakeForm;

  require("../../static/js/ui-feedback.js");

  const form = new FakeForm({ confirmMessage: "確定？" });
  const event = submitEvent(form);
  document.dispatch("submit", event);
  await Promise.resolve();

  assert.equal(event.defaultPrevented, true);
  assert.equal(event.immediateStopped, true);
  assert.equal(form.dataset.confirmed, "true");
  assert.equal(form.requestSubmitCount, 1);
});

test("ordinary form submit shows loading state and disables submit button", async () => {
  const document = new FakeEventTarget();
  document.getElementById = () => null;
  global.document = document;
  global.window = { confirm: () => true };
  global.HTMLFormElement = FakeForm;

  require("../../static/js/ui-feedback.js");

  const button = new FakeButton();
  const form = new FakeForm({ button });
  const event = submitEvent(form);
  document.dispatch("submit", event);
  await new Promise((resolve) => setTimeout(resolve, 0));

  assert.equal(button.classList.contains("is-loading"), true);
  assert.equal(button.disabled, true);
});
