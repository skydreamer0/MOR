# MOR GitHub Release Packaging Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ship MOR as clean GitHub Releases for Windows and macOS without bundling local Excel or SQLite data, while keeping the app directly runnable after download.

**Architecture:** Build per-platform release artifacts from the existing Flask/Jinja app, move mutable runtime state into a user-writable directory outside the packaged bundle, and keep source-controlled Excel/DB data out of the release archive. Use GitHub Actions to produce and attach Windows and macOS artifacts to a GitHub Release, and split independent workstreams into subagents once the runtime path contract is fixed.

**Tech Stack:** Flask, Jinja templates, SQLite, Python packaging, GitHub Actions, pytest, PowerShell, bash.

---

### Task 1: Define The Release Data Boundary

**Files:**
- Modify: `.gitignore`
- Modify: `ROADMAP.md`
- Modify: `README.md`
- Test: `tests/test_release_data_boundary.py` or an existing repo-policy test file

**Step 1: Write the failing test**

Add a guard that fails if tracked release inputs include local data files or if the app still assumes the repository root is writable for runtime data.

**Step 2: Run test to verify it fails**

Run: `D:\AI\python.exe -m pytest tests/test_release_data_boundary.py -q`

Expected: FAIL until the repo stops treating local Excel/DB files as release assets.

**Step 3: Write minimal implementation**

Remove tracked personal Excel files from the release surface, tighten ignore rules for generated data, and document that release bundles do not include source data.

**Step 4: Run test to verify it passes**

Run: `D:\AI\python.exe -m pytest tests/test_release_data_boundary.py -q`

Expected: PASS.

### Task 2: Externalize Runtime Paths

**Files:**
- Modify: `src/backend/app.py`
- Modify: `src/backend/database.py`
- Modify: `src/backend/data_loader.py`
- Create: `src/backend/runtime_paths.py` if needed
- Test: `tests/test_release_runtime_paths.py` or focused route/path tests

**Step 1: Write the failing test**

Add tests that prove the app can start with an empty release bundle and creates or uses a user-writable data directory instead of `PROJECT_ROOT` for mutable runtime files.

**Step 2: Run test to verify it fails**

Run: `D:\AI\python.exe -m pytest tests/test_release_runtime_paths.py -q`

Expected: FAIL because the current code still points at the repository root.

**Step 3: Write minimal implementation**

Introduce one path resolver for release/runtime data, keep `DB_BASE_PATH` and `DATA_BASE_PATH` overrideable, and make the SQLite workbench initialize in the writable location.

**Step 4: Run test to verify it passes**

Run: `D:\AI\python.exe -m pytest tests/test_release_runtime_paths.py -q`

Expected: PASS.

### Task 3: Add Cross-Platform Packaging

**Files:**
- Create: `.github/workflows/release.yml`
- Create: `scripts/build_release.ps1`
- Create: `scripts/build_release.sh`
- Modify: `requirements.txt` only if a runtime dependency is truly missing
- Test: packaging verification commands in CI

**Step 1: Write the failing test**

Add a workflow or smoke-level check that asserts Windows and macOS build jobs each produce exactly one distributable artifact and do not include local Excel/DB files.

**Step 2: Run test to verify it fails**

Run the release workflow locally as far as practical, or validate the workflow file structure with a focused syntax/lint check.

Expected: FAIL until the workflow and build scripts exist.

**Step 3: Write minimal implementation**

Create a matrix GitHub Actions workflow that installs dependencies, runs tests, builds Windows and macOS artifacts, and uploads them to the GitHub Release.

**Step 4: Run test to verify it passes**

Run the project test suite plus the packaging smoke checks defined by the workflow.

Expected: PASS.

### Task 4: Update User-Facing Release Docs

**Files:**
- Modify: `README.md`
- Modify: `docs/workflows/local-setup.md`
- Modify: `docs/workflows/` if a release workflow note is needed

**Step 1: Write the failing test**

Add documentation assertions only if the repo already uses doc checks; otherwise treat this as a doc-only task.

**Step 2: Run test to verify it fails**

Run the targeted doc or smoke tests that cover startup, upload, sync, and export behavior.

**Step 3: Write minimal implementation**

Document the download, first-run, sync/import, and data-storage behavior for both Windows and macOS users.

**Step 4: Run test to verify it passes**

Run: `D:\AI\python.exe -m pytest -q`

Expected: PASS.

### Parallel Subagent Split

After Task 1 establishes the runtime/data boundary, these can run in parallel:

1. Subagent A: Task 2 runtime path and database bootstrap work.
2. Subagent B: Task 3 GitHub Actions packaging and artifact work.
3. Subagent C: Task 4 release docs and user setup wording.

Each subagent should return:

- Files changed.
- Tests run.
- Any release-risk or packaging-risk notes.

### Verification Commands

Run these before shipping the release work:

```powershell
D:\AI\python.exe -m pytest -q
D:\AI\python.exe -m py_compile app.py src\backend\app.py src\backend\sales_forecast.py src\backend\forecast_config.py src\backend\forecast_models.py src\backend\data_loader.py src\backend\forecast_engine.py src\backend\exporter.py src\backend\web\form_parser.py src\backend\web\forecast_presenter.py
git ls-files "*.xlsx" "*.db" "*.sqlite" "*.sqlite3"
```
