# Forecast Item Status Layering Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Split discontinued forecast items into a collapsed section while keeping active items in the main forecast adjustment table.

**Architecture:** Treat `item_configs.item_status == "discontinued"` as the discontinued item marker. Propagate the status onto `ForecastRow`, partition rows in the forecast route, and render discontinued rows in a lower `<details>` block inside the existing export form.

**Tech Stack:** Flask, Jinja templates, SQLite item config, pytest.

---

### Task 1: Regression Test

**Files:**
- Modify: `tests/test_app.py`

**Steps:**
1. Add a route test that marks one product `item_status = "discontinued"`.
2. Request `/forecast`.
3. Assert the page renders active item rows in the main table and discontinued item rows in a collapsed discontinued section with count and last-year total.
4. Run the focused test and confirm it fails before implementation.

### Task 2: Backend Row Status

**Files:**
- Modify: `src/backend/forecast_models.py`
- Modify: `src/backend/operational_views.py`
- Modify: `src/backend/app.py`

**Steps:**
1. Add `item_status` to `ForecastRow`.
2. Populate it from `item_configs` when applying item config.
3. Partition rendered rows into active and discontinued rows in the forecast route.

### Task 3: Template Layering

**Files:**
- Modify: `templates/forecast.html`
- Modify: `templates/_forecast_row.html`

**Steps:**
1. Render active rows in the primary table body.
2. Render discontinued rows in a lower `<details>` block.
3. Add row metadata and a badge for discontinued rows.

### Task 4: Verification

**Files:**
- Test: `tests/test_app.py`

**Steps:**
1. Run the focused route test.
2. Run the full pytest suite.
3. Review `git diff`.
