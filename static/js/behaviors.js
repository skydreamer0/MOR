(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.MORBehaviors = factory();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  function bindScrollCollapse(scroller, target, opts) {
    if (!scroller || !target || !target.classList) return;
    const className = opts.className;
    const threshold = Number(opts.threshold ?? 24);
    scroller.addEventListener("scroll", () => {
      target.classList.toggle(className, scroller.scrollTop > threshold);
    }, { passive: true });
  }

  function bindDirectionalCollapse(scroller, target, opts) {
    if (!scroller || !target || !target.classList) return;
    const className = opts.className;
    const expandThreshold = Number(opts.expandThreshold ?? 8);
    let collapsed = target.classList.contains(className);

    scroller.addEventListener("wheel", (event) => {
      if (event.deltaY > 0 && !collapsed) {
        collapsed = true;
        target.classList.add(className);
      }
    }, { passive: true });

    scroller.addEventListener("scroll", () => {
      if (collapsed && scroller.scrollTop < expandThreshold) {
        collapsed = false;
        target.classList.remove(className);
      }
    }, { passive: true });
  }

  function resolveScroller(selector, target) {
    if (!selector) return null;
    if (selector.startsWith("closest:")) {
      const closestSelector = selector.slice("closest:".length);
      return target.closest(closestSelector);
    }
    return document.querySelector(selector);
  }

  function init(rootNode) {
    const scope = rootNode || document;
    scope.querySelectorAll("[data-collapse-on-scroll]").forEach((target) => {
      bindScrollCollapse(resolveScroller(target.dataset.collapseOnScroll, target), target, {
        className: target.dataset.collapseClass,
        threshold: target.dataset.collapseThreshold,
      });
    });
    scope.querySelectorAll("[data-collapse-on-wheel]").forEach((target) => {
      bindDirectionalCollapse(resolveScroller(target.dataset.collapseOnWheel, target), target, {
        className: target.dataset.collapseClass,
        expandThreshold: target.dataset.collapseExpandThreshold,
      });
    });
  }

  if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", () => init(document), { once: true });
    } else {
      init(document);
    }
  }

  return { bindScrollCollapse, bindDirectionalCollapse, init };
});
