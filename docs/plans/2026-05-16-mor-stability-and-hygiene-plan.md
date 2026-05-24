# MOR Stability And Hygiene Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Stabilize MOR's repository hygiene, date/period correctness, frontend asset loading, and regression coverage without broad refactors.

**Architecture:** Keep Flask routes thin and preserve the existing Flask/Jinja/vanilla JS shape. Each task owns a narrow write set so subagents can work without conflicts; shared files such as `src/backend/app.py` and `tests/test_app.py` are handled sequentially by the main agent or one assigned worker only.

**Tech Stack:** Python 3.11, Flask, pandas, SQLite, pytest, Jinja templates, vanilla JavaScript, CSS.

---

## Current Baseline

- Dirty files before this plan:
  - `mor_workbench.db`
  - `templates/_dashboard_metrics.html`
  - `tests/test_app.py`
- Current verification observed before this plan:
  - `D:\AI\python.exe -m pytest -q`
  - Result: `221 passed`
- Known risks:
  - Tracked local DB files can leak local state into commits.
  - Runtime package versions may differ from `requirements.txt`.
  - `ROADMAP.md` and some workflow text show mojibake in terminal output.
  - UI behavior has external CDN and duplicate script risks.

## Conflict Rules

- Only one worker may write `src/backend/app.py` or `tests/test_app.py` at a time.
- Repo hygiene, backend correctness, frontend cleanup, and ETL transaction work must be separate commits.
- Do not edit `.xlsx` source data.
- Do not remove tracked DB files from the working directory; if DB tracking is changed, use index-only removal after confirming local data should be preserved.
- Do not vendor third-party JavaScript such as HTMX unless explicitly approved.

## Parallelization Map

- Safe in parallel after Task 0:
  - Task 1 repo hygiene planning/docs/index work.
  - Task 4 frontend CSS/script cleanup, if it avoids `tests/test_app.py` until review.
  - Task 6 ETL transaction tests and implementation.
- Must be sequential:
  - Task 2 period validation before Task 3 projection/cache work.
  - Task 3 projection/cache before Task 5 row identity migration, because both may touch app context tests.
  - Any edit to `tests/test_app.py`.

---

### Task 0: Baseline Guard

**Files:**
- Inspect: `git status --short`
- Inspect: `requirements.txt`
- Inspect: `docs/workflows/local-setup.md`

**Step 1: Capture current git state**

Run:

```powershell
git status --short
git diff --stat
```

Expected: show existing dirty DB/template/test files plus this plan file.

**Step 2: Confirm tests still collect**

Run:

```powershell
D:\AI\python.exe -m pytest --collect-only -q
```

Expected: `221 tests collected` or a reviewed intentional change.

**Step 3: Commit boundary**

Do not commit baseline unless the user asks. This task exists to avoid mixing existing user changes with implementation work.

---

### Task 1: Repo Hygiene And DB Tracking

**Files:**
- Modify: `.gitignore`
- Modify index only: `mor_workbench.db`
- Possibly modify index only: `.test-dbs/**/mor_workbench.db`
- Modify docs if needed: `docs/workflows/local-setup.md`

**Step 1: Identify tracked database files**

Run:

```powershell
git ls-files | Where-Object { $_ -match '\.(db|sqlite|sqlite3)$' }
```

Expected: list any tracked local or test DB files.

**Step 2: Update ignore rules**

Add explicit local DB ignore rules if missing:

```gitignore
mor_workbench.db
.test-dbs/
*.sqlite
*.sqlite3
```

Do not ignore source Excel files.

**Step 3: Stop tracking local DB files without deleting them**

Run only after confirming the listed DB files are local state:

```powershell
git rm --cached mor_workbench.db
git ls-files .test-dbs | ForEach-Object { git rm --cached -- $_ }
```

Expected: DB files become staged deletions from Git index but remain on disk.

**Step 4: Verify app/test DB initialization**

Run:

```powershell
D:\AI\python.exe -m pytest -q tests/test_app.py -k "empty_db or read_excel"
D:\AI\python.exe -m pytest -q
```

Expected: tests pass without requiring tracked DB files.

---

### Task 2: Unified Target Period Validation

**Files:**
- Modify: `src/backend/web/form_parser.py`
- Modify: `src/backend/app.py`
- Test: `tests/test_form_parser.py`
- Test: `tests/test_ui_smoke.py`
- Avoid broad edits to: `tests/test_app.py`

**Step 1: Write failing validation tests**

Add focused tests for:

- Non-numeric year/month.
- Empty year/month.
- Month outside `1..12`.
- Year outside the intended MOR range.
- POST export invalid period returns a controlled 400 or validation response, not 500.

Run:

```powershell
D:\AI\python.exe -m pytest -q tests/test_form_parser.py tests/test_ui_smoke.py -k "target_period or YearMonthRangeValidation"
```

Expected: new tests fail before implementation.

**Step 2: Implement one shared validator**

Create or update a single helper in `src/backend/web/form_parser.py`:

```python
def validate_target_period(year: int, month: int) -> None:
    if not 2000 <= year <= 2100:
        raise ValueError("year must be between 2000 and 2100")
    if not 1 <= month <= 12:
        raise ValueError("month must be between 1 and 12")
```

Use it from `parse_target_period()` and replace route-level hand-written checks in `src/backend/app.py`.

**Step 3: Verify focused behavior**

Run:

```powershell
D:\AI\python.exe -m pytest -q tests/test_form_parser.py tests/test_ui_smoke.py
```

Expected: pass.

---

### Task 3: Projection `as_of` And Cache Key

**Files:**
- Modify: `src/backend/operational_views.py`
- Modify: `src/backend/app.py`
- Test: `tests/test_projection_engine.py`
- Test: `tests/test_operational_views.py`
- Sequential if touching: `tests/test_app.py`

**Step 1: Write failing tests for deterministic projection date**

Add tests for:

- Past target month uses a stable month-end or close-date `as_of`.
- Current target month can use today's date.
- Future target month does not accidentally use today's elapsed workdays as if the month were active.
- Cache key changes when projection `as_of` changes.

Run:

```powershell
D:\AI\python.exe -m pytest -q tests/test_projection_engine.py tests/test_operational_views.py -k "as_of or projection or cache"
```

Expected: at least one new test fails.

**Step 2: Add explicit `as_of` plumbing**

Update context building so projection date is passed explicitly instead of hidden inside `date.today()`.

Implementation direction:

- Add an `as_of` parameter to `build_forecast_page_context(...)`.
- Compute route-level `as_of` once in `src/backend/app.py`.
- Include `as_of.isoformat()` in context cache keys when projection output depends on it.

**Step 3: Verify focused behavior**

Run:

```powershell
D:\AI\python.exe -m pytest -q tests/test_projection_engine.py tests/test_operational_views.py tests/test_app.py -k "projection or cache or forecast_page_context"
```

Expected: pass.

---

### Task 4: Frontend Asset And Token Cleanup

**Files:**
- Modify: `templates/_head_assets.html`
- Modify: `templates/customers.html`
- Modify: `templates/forecast.html`
- Modify: `templates/product_monitor.html`
- Modify: `static/css/mor.css`
- Modify: `static/js/forecast-table.js`
- Modify: `static/js/monitor-table.js`
- Possibly create: `static/js/customers-table.js`
- Test: `tests/test_app.py` only after all template edits are stable.

**Step 1: Remove duplicate analytics script load**

Remove the page-level duplicate `analytics-renderer.js` include from `templates/customers.html` if `_head_assets.html` already loads it globally.

Run:

```powershell
D:\AI\python.exe -m pytest -q tests/test_app.py -k "customers or dashboard"
```

Expected: pass.

**Step 2: Normalize CSS token usage**

Replace undefined tokens with existing design tokens in `static/css/mor.css`:

- `--border` -> `--line`
- `--surface` -> `--panel`
- `--surface-2` -> `--surface-subtle`
- `--text` -> `--ink`
- `--radius` -> existing radius token or fixed local radius already used nearby.

Run:

```powershell
D:\AI\python.exe -m pytest -q tests/test_app.py -k "css or design or dashboard"
```

Expected: pass.

**Step 3: Move inline behavior into static JS**

Move only low-risk page behavior:

- file picker label updates.
- toolbar collapse behavior.
- customer detail expand/collapse.
- `data-confirm-message` submit confirmation.

Do not change HTMX row patch behavior in this task.

Run:

```powershell
node --check static\js\forecast-table.js
node --check static\js\monitor-table.js
if (Test-Path static\js\customers-table.js) { node --check static\js\customers-table.js }
D:\AI\python.exe -m pytest -q tests/test_app.py
```

Expected: pass.

**Step 4: Browser verification**

Run the app:

```powershell
D:\AI\python.exe app.py
```

Check:

- `/`
- `/forecast`
- `/monitor/products`
- `/customers`
- `/settings`

Expected: Chinese labels render, console has no duplicate/undefined script errors, filters work, manual quantity updates total, customer detail charts render, narrow toolbar does not overlap.

---

### Task 5: Row Identity Delimiter Hardening

**Files:**
- Modify: `src/backend/forecast_engine.py`
- Modify: `src/backend/app.py`
- Modify only if needed: `src/backend/history_service.py`
- Modify only if needed: `src/backend/daily_sales_importer.py`
- Modify only if needed: `src/backend/projection_engine.py`
- Modify only if needed: `src/backend/monthly_review.py`
- Test: `tests/test_forecast.py`
- Test: `tests/test_projection_engine.py`
- Test: `tests/test_monthly_review.py`
- Sequential if touching: `tests/test_app.py`

**Step 1: Write delimiter regression tests**

Add tests for customer and product values containing `__`.

Minimum assertions:

- Manual adjustment writes to the correct customer/product.
- Export and projection do not merge two different rows.
- Monthly review remains keyed to the intended row.

Run:

```powershell
D:\AI\python.exe -m pytest -q tests/test_forecast.py tests/test_projection_engine.py tests/test_monthly_review.py -k "row_id or delimiter or adjustment"
```

Expected: new tests fail if current split logic is vulnerable.

**Step 2: Centralize row key encoding**

Add a small helper in the most local existing module, likely `src/backend/forecast_engine.py`, for encoding and decoding row identity.

Implementation direction:

- Preserve compatibility with existing form values during transition.
- Avoid raw `split("__", 1)` outside the helper.
- Keep the exported workbook schema unchanged.

**Step 3: Verify focused behavior**

Run:

```powershell
D:\AI\python.exe -m pytest -q tests/test_forecast.py tests/test_projection_engine.py tests/test_monthly_review.py tests/test_app.py -k "row_id or delimiter or adjustment or export"
```

Expected: pass.

---

### Task 6: ETL Cleanup Transaction Decision

**Files:**
- Modify: `src/backend/etl.py`
- Test: `tests/test_etl.py`
- Test: `tests/test_current_month_integration.py`

**Step 1: Decide intended cleanup semantics**

Choose one behavior before coding:

- Option A: cleanup failure rolls back the whole sync.
- Option B: sync commits and cleanup failure is logged as a data-health warning.

Prefer Option A only if cleanup is part of correctness, not best-effort maintenance.

**Step 2: Write rollback or warning test**

Run:

```powershell
D:\AI\python.exe -m pytest -q tests/test_etl.py tests/test_current_month_integration.py -k "rollback or cleanup or sync_excel_to_db"
```

Expected: new test fails before implementation.

**Step 3: Implement minimal behavior**

Update `sync_excel_to_db()` and `_clear_covered_current_month_records()` flow according to the chosen semantics.

Do not overwrite `.xlsx` files.

**Step 4: Verify focused behavior**

Run:

```powershell
D:\AI\python.exe -m pytest -q tests/test_etl.py tests/test_current_month_integration.py
```

Expected: pass.

---

### Task 7: Documentation And Final Verification

**Files:**
- Modify if behavior changed: `docs/workflows/local-setup.md`
- Modify if UI workflow changed: `docs/workflows/operational-interface.md`
- Modify if task priority changed: `ROADMAP.md`

**Step 1: Update only active docs**

Update docs only for actual user-visible or workflow changes made in Tasks 1-6.

Do not read or update `docs/archive/` or `superseded-*` files.

**Step 2: Run full verification**

Run:

```powershell
D:\AI\python.exe -m py_compile app.py src\backend\app.py src\backend\sales_forecast.py src\backend\forecast_config.py src\backend\forecast_models.py src\backend\data_loader.py src\backend\forecast_engine.py src\backend\projection_engine.py src\backend\operational_views.py src\backend\etl.py src\backend\exporter.py src\backend\web\form_parser.py src\backend\web\forecast_presenter.py
D:\AI\python.exe -m pytest -q
```

Expected: all commands pass.

**Step 3: Review diff before commit**

Run:

```powershell
git diff --stat
git diff --check
```

Expected: no whitespace errors and no unrelated files.

---

## Suggested Commit Sequence

1. `docs(plan): add MOR stability and hygiene plan`
2. `chore(repo): stop tracking local database files`
3. `fix(period): centralize target period validation`
4. `fix(projection): make forecast projection date explicit`
5. `fix(ui): stabilize shared assets and design tokens`
6. `fix(forecast): harden row identity parsing`
7. `fix(etl): define current-month cleanup transaction behavior`
8. `docs(workflow): update MOR setup and operational notes`

## Execution Options

1. **Subagent-driven in this session:** assign one fresh worker per task, with disjoint write ownership and main-agent review between tasks.
2. **Sequential local execution:** main agent executes Task 1 through Task 7 one at a time, safest for shared files.
3. **Hybrid:** parallelize Task 1, Task 4, and Task 6 only; keep Tasks 2, 3, and 5 sequential.

Recommended: Hybrid. It gives speed without letting multiple agents touch `src/backend/app.py` or `tests/test_app.py` at the same time.
