# MOR Refactor Plan

**Context:** Personal-use Flask revenue-monitoring app. No multi-user, no security hardening needed.
Goals: faster page loads, less noisy code, easier to extend.

Priorities in order: (1) correctness of calculated values, (2) response speed, (3) code navigability.
Do NOT introduce Repository patterns, dependency injection, or test harnesses — over-engineering for this use case.

---

## Task 1 — Inline `product_monitor_workflow.py` into `app.py`

**Why:** It is a genuine pass-through. Its only function `build_product_monitor_template_context` builds a
plain dict with no validation, no transformation, and no business logic. Deletion test passes: 0 complexity
migrates to callers — they just build the dict inline.

**Files touched:**
- `src/backend/product_monitor_workflow.py` — delete entirely
- `src/backend/app.py` — inline the dict-building where `build_product_monitor_template_context` is called

**How:**
1. In `app.py`, find the import of `build_product_monitor_template_context` and remove it.
2. Find every call site of `build_product_monitor_template_context(context, db, ...)` in `app.py`.
3. Replace each call with the equivalent inline dict (copy the body of the function verbatim, substituting
   the local variable names at each call site).
4. Delete `src/backend/product_monitor_workflow.py`.
5. Delete `tests/test_product_monitor_workflow.py` (it only tests the wrapper, not real logic).

**Expected outcome:** One fewer file, one fewer import chain, zero behaviour change.

---

## Task 2 — Centralise amount calculation

**Why:** The rule "convert forecast quantity → financial amount" has at least three divergent implementations:
- `operational_views._dashboard_amount()` → `_amount_from_latest_order_price()` → price-quantity ratio path
- `operational_views.recalculate_forecast_amounts()` → uses `row.estimated_amount` directly
- `forecast_models.ForecastRow` (line ~70) — `final_forecast * latest_price` simple multiply
- Budget fallback in `_to_monthly_review_row`: `budget_amount if > 0 else quantity × price`

A discrepancy in any one path produces wrong numbers silently. The user cares about correct totals.

**Files touched:**
- `src/backend/operational_views.py` — consolidate `_dashboard_amount`, `_amount_from_latest_order_price`,
  `_latest_price_quantity` into a single top-level function `row_amount(row: ForecastRow) -> float`
- Every call site that currently computes `qty * price` or calls `_dashboard_amount` inline

**How:**
1. Read all four paths carefully and identify the canonical logic (the price-quantity ratio path in
   `_amount_from_latest_order_price` is the most complete — it handles the ratio fallback).
2. Write `row_amount(row: ForecastRow) -> float` at the top of `operational_views.py`, implementing the
   canonical path.
3. Replace all four divergent implementations with calls to `row_amount(row)`.
4. Grep for `latest_price` and `price_quantity` across the codebase to catch any remaining call sites.
5. Run the app and verify the dashboard totals match what they did before (spot-check two months).

**Expected outcome:** One place to change if pricing logic ever changes. Totals consistent across dashboard,
export, and monthly review.

---

## Task 3 — Audit `operational_views.py` for dead / duplicated load functions

**Why:** The file is 1 059 lines. Some load functions may be called from only one place or be superseded
by newer data paths. Removing dead weight makes the hot path faster (fewer imports, smaller bytecode) and
easier to navigate.

**Files touched:**
- `src/backend/operational_views.py`

**How:**
1. For each top-level function in `operational_views.py`, run a grep across `src/` and `tests/` to count
   call sites.
2. Any function with 0 external call sites (only called within the file itself) — examine whether it is
   used transitively from an exported function. If not, delete it.
3. Any function that is a thin delegator to another function in the same file — inline it.
4. Do not restructure dataclasses (`BudgetTarget`, `DashboardMetrics`, `ProductMonitorRow`, etc.) — they
   are stable and widely referenced.

**Expected outcome:** Smaller file, reduced import surface, no behaviour change.

---

## Task 4 — Verify cache invalidation correctness (read-only audit, no code change)

**Why:** The cache (`flask_caching.SimpleCache`) uses version-counter keys built by `_make_cache_key`.
If any write path (save_row_override, sync, item config update, daily import, close-month) fails to call
`_invalidate_context_cache` or `_invalidate_all_context_cache`, the user will see stale data after saving.
This is the most common source of "I saved but the page still shows old values" bugs.

**Files touched:** `src/backend/app.py` (read only)

**How:**
1. List every Flask route that writes to the database (INSERT, UPDATE, DELETE).
2. For each such route, verify it calls either `_invalidate_context_cache(year, month)` or
   `_invalidate_all_context_cache()` before returning.
3. Produce a table: route → write operation → invalidation call present (yes/no).
4. If any row shows "no", add the missing invalidation call.

**Expected outcome:** User never sees stale data after a write. No structural change needed if all routes
already invalidate correctly.

---

## Execution order

1. Task 1 (inline product_monitor_workflow) — 15 min, zero risk, do first for a clean win.
2. Task 4 (cache audit) — read-only, do second to surface any stale-data bugs before touching more code.
3. Task 2 (centralise amount) — moderate risk, do after Task 4 so the baseline is verified.
4. Task 3 (dead code audit in operational_views) — do last, lowest risk, mechanical grep work.

---

## Explicitly out of scope

- Repository / DataRepository pattern — unnecessary for single-user SQLite use.
- Splitting `operational_views.py` into multiple modules — deferred; not worth the import churn until
  the file is a real navigation problem (it isn't yet for a single developer).
- `forecast_export_workflow`, `forecast_write_workflow`, `item_settings_workflow`,
  `dashboard_analytics_workflow` — these contain real logic (form validation, SQL writes, template context
  assembly with filtering/sorting). Do not inline them; their abstraction is earning its keep.
- Any test infrastructure changes — the existing test suite is fine as-is for personal use.
