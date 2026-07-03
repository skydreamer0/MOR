# MOR Architecture Deepening Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use `subagent-driven-development` to implement this plan task-by-task after the user confirms execution.

**Goal:** Deepen the MOR backend modules identified in the 2026-07-03 architecture review while following `ROADMAP.md`: one seam at a time, stable behavior, characterization tests first.

**Architecture:** Keep Flask routes, templates, DB schema, Excel schema, and user-visible behavior stable. Add narrow backend modules or typed interfaces that concentrate repeated read/orchestration rules behind deeper interfaces. Prefer compatibility during migration; remove old direct access only after focused tests pass.

**Tech Stack:** Flask/Jinja, SQLite via `MORDatabase`, pandas, pytest, vanilla JavaScript unchanged.

---

## Execution Rules

- Do not read `docs/archive/` or any `superseded-*` file.
- Do not change `.xlsx` source data.
- Do not change DB schema, Excel labels, routes, templates, or forecast math unless a later task explicitly asks.
- Keep every implementation batch small enough for focused tests.
- Use subagents for investigation, implementation, and review, but the main agent owns integration.
- Run focused tests after each batch; run full `D:\AI\python.exe -m pytest -q` before claiming the whole goal is complete.
- If a batch touches more than three production modules with major rewrites, stop and split it.

## Goal Batch Order

1. Monthly Review data read seam.
2. Workbench input interface.
3. Product Monitor month context.
4. Active documentation alignment.
5. Architecture guards and final validation.

---

## Task 1: Monthly Review Data Read Seam

**Goal:** Add a read-only Monthly Review data module so closed-month fallback, product names, price quantities, budgets, and forecast amount reads stop being repeated across Monthly Review modules.

**Files:**
- Create: `src/backend/monthly_review_data.py`
- Create: `tests/test_monthly_review_data.py`
- Later modify in small slices:
  - `src/backend/monthly_review_trend.py`
  - `src/backend/monthly_review_forecast_bias.py`
  - `src/backend/monthly_review_actions.py`
  - `src/backend/monthly_review_customers.py`
  - `src/backend/monthly_review_products.py`
  - `src/backend/monthly_review.py`
- Later modify: `tests/test_architecture_imports.py`

**Interface Shape:**

```python
@dataclass(frozen=True)
class MonthlyReviewDataReader:
    db: MORDatabase

    def close_record(self, year: int, month: int) -> dict | None: ...
    def reviewable_months(self) -> list[tuple[int, int]]: ...
    def customer_amounts(self, year: int, month: int) -> dict[str, float]: ...
    def product_totals(self, year: int, month: int) -> tuple[dict[str, float], dict[str, float], dict[str, str]]: ...
    def budget_rows(self, year: int, month: int) -> dict[str, dict]: ...
    def product_names(self) -> dict[str, str]: ...
    def price_quantities(self) -> dict[str, float]: ...
    def quantity_multiplier(self, product_code: str) -> float: ...
    def snapshot_forecasts(self, year: int, month: int) -> dict[str, dict]: ...
    def forecast_amounts(self, year: int, month: int, *, historical_fallback: bool = False) -> dict[tuple[str, str], float]: ...
```

**Steps:**

1. Add `tests/test_monthly_review_data.py` characterization tests for:
   - closed month reads from `daily_sales_actuals`;
   - open month falls back to `sales_records`;
   - product-name fallback order;
   - `price_quantity` multiplier;
   - forecast amount with and without historical fallback.
2. Implement `monthly_review_data.py` with existing SQL copied exactly where practical.
3. Migrate `monthly_review_trend.py` and `monthly_review_forecast_bias.py` to share `price_quantities`, `quantity_multiplier`, and forecast amount reads.
4. Migrate closed/open fallback reads in `monthly_review_actions.py`, `monthly_review_customers.py`, `monthly_review_products.py`, and `monthly_review_trend.py`.
5. Migrate `monthly_review.py` last, preserving its historical forecast unit-price fallback.
6. Add an architecture guard that source-table Monthly Review SQL lives in `monthly_review_data.py` after migration.

**Verification:**

```powershell
D:\AI\python.exe -m pytest tests\test_monthly_review_data.py tests\test_monthly_review.py tests\test_monthly_review_actions.py tests\test_monthly_review_customers.py tests\test_monthly_review_products.py tests\test_monthly_review_forecast_bias.py tests\test_monthly_review_trend.py tests\test_monthly_review_context.py -q --basetemp=.pytest-tmp
```

**Risk:** Medium-low. Protect amount semantics, `price_quantity` conversion, and the difference between `historical_fallback=True` and `False`.

---

## Task 2: Workbench Input Interface

**Goal:** Keep `load_forecast_workbench_inputs(db, target)` stable but add a row-facing interface so `forecast_workbench_context.py` no longer reaches into raw DB-shaped maps.

**Files:**
- Modify: `src/backend/forecast_workbench_inputs.py`
- Modify: `src/backend/forecast_workbench_context.py`
- Modify: `tests/test_forecast_workbench_inputs.py`
- Modify: `tests/test_forecast_workbench_helpers.py`
- Later modify: `tests/test_architecture_imports.py`

**Interface Shape:**

```python
@dataclass(frozen=True)
class ForecastRowMonthInput:
    manual_adjustment: float | None
    adjustment_reason: str | None
    current_budget: BudgetTarget
    budget_monthly: list[float]
    budget_monthly_amount: list[float]
    price_quantity: float
    item_status: str
    is_budgeted: bool
    is_visible: bool

class ForecastWorkbenchInputs:
    def row_month_input(self, row_id: str, product_code: str) -> ForecastRowMonthInput: ...
    def visible_product(self, product_code: str) -> bool: ...
    @property
    def forecast_excluded_product_ids(self) -> frozenset[str]: ...
    @property
    def company_budgets(self) -> list[BudgetTarget]: ...
    @property
    def available_budget_months(self) -> list[tuple[int, int]]: ...
```

**Steps:**

1. Add characterization tests in `tests/test_forecast_workbench_inputs.py` for row-level lookup:
   manual quantity, reason, visibility, budgeted status, price quantity, item status, monthly budgets, and daily actuals.
2. Add typed row-facing methods/properties while keeping existing fields and helper functions compatible.
3. Migrate `forecast_workbench_context.py` to ask the interface questions instead of reading `.item_configs`, `.budget_targets`, `.budget_year_map`, `.budget_year_amount_map`, `.manual_adjustments`, `.adjustment_reasons`, and `.budget_months` directly.
4. Preserve the budget distinction:
   - dashboard company budget totals use raw budget targets;
   - row-level forecast budgets are zeroed when item settings say `is_budgeted=False`.
5. Add an architecture guard that `forecast_workbench_context.py` does not access the raw input maps directly.

**Verification:**

```powershell
D:\AI\python.exe -m pytest tests\test_forecast_workbench_inputs.py tests\test_forecast_workbench_helpers.py tests\test_architecture_imports.py -q --basetemp=.pytest-tmp
D:\AI\python.exe -m pytest tests\test_app.py -q --basetemp=.pytest-tmp
```

**Risk:** Medium-low. Budget semantics are subtle; keep company budget totals raw and row-level enrichment filtered.

---

## Task 3: Product Monitor Month Context

**Goal:** Move Product Monitor month-view orchestration out of `forecast_workbench_context.py` without moving projection math, monitor row calculation, dashboard KPI math, or calendar logic.

**Files:**
- Create: `src/backend/product_monitor_month_context.py`
- Create: `tests/test_product_monitor_month_context.py`
- Modify: `src/backend/forecast_workbench_context.py`
- Later modify: `tests/test_architecture_imports.py`

**Interface Shape:**

```python
@dataclass(frozen=True)
class ProductMonitorMonthContext:
    projections: dict[str, ProjectionResult]
    dashboard: DashboardMetrics
    monitor_rows: list[ProductMonitorRow]

def build_product_monitor_month_context(
    *,
    db,
    rows: list[ForecastRow],
    daily_actuals: Mapping[str, DailyActualAggregate],
    company_budgets: Iterable[BudgetTarget],
    target: ForecastTarget,
    today: date,
    amount_for_quantity: AmountForQuantity,
) -> ProductMonitorMonthContext: ...
```

**Steps:**

1. Add characterization test proving dashboard metrics and monitor rows both use the same projection result.
2. Implement `product_monitor_month_context.py` by moving only orchestration:
   - `ensure_calendar_year(db, today.year)`;
   - `batch_project_eom(...)`;
   - `build_dashboard_metrics(...)`;
   - `build_product_monitor_rows(...)`.
3. Replace the projection/dashboard/monitor block in `forecast_workbench_context.build()`.
4. Remove `_build_projections` from `forecast_workbench_context.py`.
5. Add an architecture guard if the new seam needs protection.

**Verification:**

```powershell
D:\AI\python.exe -m pytest tests\test_product_monitor_month_context.py tests\test_forecast_workbench_helpers.py tests\test_product_monitor_rows.py tests\test_projection_engine.py tests\test_product_monitor_workflow.py -q --basetemp=.pytest-tmp
```

**Risk:** Low-medium. Keep calendar-year behavior unchanged in the first slice; do not alter projection formula or quantity scaling.

---

## Task 4: Active Documentation Alignment

**Goal:** Make active docs agree that MOR is DB-first while keeping historical migration detail out of implementation context.

**Files:**
- Modify: `docs/design/data-model.md`
- Modify: `docs/design/data-contract.md`
- Modify: `docs/architecture/current-architecture.md`
- Modify if needed: `ROADMAP.md`
- Do not edit: `docs/archive/**`
- Do not use as authority: encoding-damaged `docs/adr/003-move-to-sqlite-database.md`

**Steps:**

1. Update `docs/design/data-model.md` so Current Reality says SQLite workbench DB is active; Excel is parsed only by explicit sync/import flows.
2. Update Forecast row terminology only where it conflicts with current code (`system_forecast`, `manual_adjustment`, `final_forecast`).
3. Update `docs/design/data-contract.md` to distinguish source Excel contract from DB-first runtime contract.
4. Add a short note in `docs/architecture/current-architecture.md` if a new module from Tasks 1-3 becomes an active service.
5. Update `ROADMAP.md` only after a production seam lands, not before.

**Verification:**

```powershell
D:\AI\python.exe -m py_compile app.py src\backend\app.py src\backend\forecast_workbench_context.py src\backend\monthly_review_context.py src\backend\settings_context.py
```

**Risk:** Low. Main risk is reviving stale Excel-first language; keep docs concise and current.

---

## Task 5: Final Architecture Guards And Full Validation

**Goal:** Prevent the new seams from drifting back into shallow modules.

**Files:**
- Modify: `tests/test_architecture_imports.py`
- Review: `ROADMAP.md`
- Review: `docs/architecture/current-architecture.md`

**Steps:**

1. Add guards only after each seam migration is complete.
2. Guard Monthly Review source-table SQL placement if practical.
3. Guard Workbench raw input map access after interface migration.
4. Guard Product Monitor orchestration import path if needed.
5. Update `ROADMAP.md` completed seams after tests pass.
6. Run full validation.

**Verification:**

```powershell
D:\AI\python.exe -m pytest -q --basetemp=.pytest-tmp
```

**Risk:** Medium. Architecture guards should protect useful seams, not freeze implementation details too early.

---

## Subagent Execution Plan

Use one implementation subagent per task, not multiple implementation subagents editing the same files in parallel.

For each task:

1. Main agent gives the subagent the exact task section above.
2. Implementer subagent writes tests first, implements the smallest slice, runs focused tests, and reports changed files.
3. Fresh reviewer subagent checks spec compliance.
4. Fresh reviewer subagent checks code quality.
5. Main agent integrates, runs focused tests, and updates this plan/ROADMAP only when behavior is stable.

Parallel use is allowed for read-only review or independent docs review, not for overlapping code edits.

## Initial File Scope Before Implementation

Before Task 1 edits, inspect/change only:

- `src/backend/monthly_review.py`
- `src/backend/monthly_review_actions.py`
- `src/backend/monthly_review_customers.py`
- `src/backend/monthly_review_products.py`
- `src/backend/monthly_review_forecast_bias.py`
- `src/backend/monthly_review_trend.py`
- `tests/test_monthly_review*.py`
- `tests/test_architecture_imports.py`

