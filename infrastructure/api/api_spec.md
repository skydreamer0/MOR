# API Specification

## Overview
MOR is primarily a Server-Side Rendered (SSR) application using standard HTML forms. As such, it relies on traditional HTTP GET and POST routes. In the future, if the UI requires asynchronous operations (like previewing calculation totals without exporting), JSON APIs will be introduced.

## Base URL
Local: `http://localhost:5000`

---

## Current Routes

### 1. View Forecast Review Dashboard
Loads the application, processes the local Excel file, and returns the interactive review table.

- **URL:** `/`
- **Method:** `GET`
- **Response Type:** `text/html`
- **Success Response:**
  - **Code:** `200 OK`
  - **Content:** Jinja template rendered with `ForecastSummary`.
- **Error States:**
  - `200 OK` (with alert message): Source Excel file missing or missing columns.

### 2. Export Forecast
Accepts the user's manual adjustments and exclusions from the table and downloads the `.xlsx` workbook.

Current implementation reloads the source Excel file and rebuilds the baseline forecast before applying posted manual quantities and exclusions. This is acceptable for the prototype, but it is not the target authority model.

Target behavior: export should use the reviewed state submitted by the user as the authority. The server may recalculate effective quantities and amounts from posted values, but it must not silently replace reviewed rows with a newly generated baseline.

- **URL:** `/export`
- **Method:** `POST`
- **Request Type:** `application/x-www-form-urlencoded`
- **Form Parameters:**
  - `year` (int, required): Target forecasting year.
  - `month` (int, required): Target forecasting month.
  - `forecast_signature` (string, optional but emitted by the review page): Baseline signature used to reject stale review exports.
  - `manual_quantity__<row_id>` (float, optional): Manually specified quantity override.
  - `exclude__<row_id>` (bool, optional): If checked, sets the row output to 0.
- **Open Design Issue:**
  - The current signature detects changed regenerated baselines. A future server-side review snapshot or full submitted row payload may be needed if the workflow must export without rebuilding from Excel.
- **Success Response:**
  - **Code:** `200 OK`
  - **Content-Type:** `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
  - **Headers:** `Content-Disposition: attachment; filename=...`
- **Error States:**
  - **Code:** `400 Bad Request`
  - **Reason:** Invalid manual quantity format, invalid year/month, submitted row id not present in the regenerated forecast summary, or stale `forecast_signature`.

---

## Future JSON API (Proposed)

If rich client-side previews or headless workflows are required:

### 1. Preview Adjustments
- **URL:** `/api/v1/forecast/preview`
- **Method:** `POST`
- **Request Body:** JSON representing `manual_quantities` and `excluded_ids`.
- **Response:** JSON serialized `ForecastSummary` containing the re-calculated totals.
