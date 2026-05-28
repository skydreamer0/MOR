# UI Navigation And Route Repair Design

## Goal

Make the MOR frontend navigation consistent across pages and restore the missing exclusion-management workflow.

## Design

Use one shared Jinja header partial for the page title, primary tabs, optional sync action, and optional period controls. The tab order is 工作台, 品項管理, 排除管理, with `aria-current="page"` marking the active page.

Restore `/exclusions` and `/exclusions/save` using the existing item configuration table and helper functions. Keep the page dense and table-first, matching the current MOR design system.

Add a lightweight SQLite migration for older local databases whose `forecast_adjustments` table lacks `updated_by`, so forecast autosave does not fail against existing workbench files.

## Verification

Add regression tests before implementation for:

- `GET /exclusions` rendering the exclusion page.
- `POST /exclusions/save` saving exclusions.
- Shared header tabs and active page state on each frontend page.
- `POST /adjustments/save` working against a pre-existing old adjustment table schema.

Run the app test file and the full pytest suite after implementation.
