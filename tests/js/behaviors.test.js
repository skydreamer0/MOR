"use strict";
// node --test tests/js/  (wrapped by tests/test_frontend_js.py)
const { test } = require("node:test");
const assert = require("node:assert/strict");

const Behaviors = require("../../static/js/behaviors.js");

function makeClassList() {
  const classes = new Set();
  return {
    add(name) { classes.add(name); },
    remove(name) { classes.delete(name); },
    toggle(name, force) {
      if (force) classes.add(name);
      else classes.delete(name);
    },
    contains(name) { return classes.has(name); },
  };
}

function makeScroller({ scrollTop = 0 } = {}) {
  const listeners = {};
  return {
    scrollTop,
    listeners,
    addEventListener(type, handler, options) {
      listeners[type] = { handler, options };
    },
  };
}

test("bindScrollCollapse toggles target class when scrollTop crosses threshold", () => {
  const target = { classList: makeClassList() };
  const scroller = makeScroller();

  Behaviors.bindScrollCollapse(scroller, target, { className: "is-collapsed", threshold: 24 });

  scroller.scrollTop = 25;
  scroller.listeners.scroll.handler();
  assert.equal(target.classList.contains("is-collapsed"), true);

  scroller.scrollTop = 8;
  scroller.listeners.scroll.handler();
  assert.equal(target.classList.contains("is-collapsed"), false);
  assert.deepEqual(scroller.listeners.scroll.options, { passive: true });
});

test("bindDirectionalCollapse collapses on downward wheel and expands near top", () => {
  const target = { classList: makeClassList() };
  const scroller = makeScroller({ scrollTop: 20 });

  Behaviors.bindDirectionalCollapse(scroller, target, { className: "is-collapsed", expandThreshold: 8 });

  scroller.listeners.wheel.handler({ deltaY: 1 });
  assert.equal(target.classList.contains("is-collapsed"), true);

  scroller.scrollTop = 7;
  scroller.listeners.scroll.handler();
  assert.equal(target.classList.contains("is-collapsed"), false);
});
