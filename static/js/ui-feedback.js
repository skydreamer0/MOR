/* ── Shared confirm dialog + form submit loading state ───────── */
(function () {
  "use strict";

  function appConfirm(opts) {
    const dlg = document.getElementById("app-confirm");
    if (!dlg || typeof dlg.showModal !== "function") {
      return Promise.resolve(window.confirm(opts.message));
    }
    dlg.querySelector("[data-confirm-title]").textContent = opts.title || "確認操作";
    dlg.querySelector("[data-confirm-message]").textContent = opts.message || "";
    dlg.querySelector("[data-confirm-ok]").textContent = opts.okLabel || "確認";
    return new Promise((resolve) => {
      dlg.addEventListener("close", () => resolve(dlg.returnValue === "ok"), { once: true });
      dlg.showModal();
    });
  }

  window.appConfirm = appConfirm;

  document.addEventListener("submit", (e) => {
    const form = e.target;
    if (!(form instanceof HTMLFormElement) || !form.dataset.confirm) return;
    if (form.dataset.confirmed === "true") {
      form.dataset.confirmed = "";
      return;
    }
    e.preventDefault();
    e.stopImmediatePropagation();
    appConfirm({
      title: form.dataset.confirmTitle,
      message: form.dataset.confirm,
      okLabel: form.dataset.confirmOk,
    }).then((ok) => {
      if (!ok) return;
      form.dataset.confirmed = "true";
      form.requestSubmit();
    });
  }, true);

  document.addEventListener("submit", (e) => {
    if (e.defaultPrevented) return;
    const form = e.target;
    if (!(form instanceof HTMLFormElement) || form.dataset.noLoading === "true") return;
    const btn = form.querySelector('button[type="submit"], button:not([type])');
    if (!btn) return;
    btn.classList.add("is-loading");
    setTimeout(() => { btn.disabled = true; }, 0);
  });
})();
