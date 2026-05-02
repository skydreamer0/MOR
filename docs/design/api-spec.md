# MOR API Spec

## Status

This document describes the current and future backend endpoints for MOR.

## Current Public Routes

### `GET /`

Purpose:
Render the forecast review page for the selected month.

Behavior:

- Load the Excel source workbook.
- Build the forecast summary.
- Render the review table and summary metrics.
- Show a friendly error message when the workbook is missing or invalid.

### `POST /export`

Purpose:
Validate the reviewed forecast state and generate the final Excel workbook.

Important:

- `POST /export` must not silently regenerate baseline forecast quantities.
- The backend may validate, normalize, and export the submitted reviewed state.
- Exported workbook contents must follow the submitted UI state.

## Future JSON API

Future JSON endpoints are optional and should only be added if the UI needs richer async preview or bootstrapping behavior.

Proposed endpoints:

### `GET /api/forecast`

Purpose:
Return a JSON-safe forecast summary and review-grid metadata.

### `POST /api/forecast/preview`

Purpose:
Return a validated preview of the submitted reviewed state before export.

## API Rules

- Dates should be serialized as ISO strings.
- Validation errors should be structured and user-readable.
- JSON endpoints should reuse the same adjustment and validation rules as the form workflow.
- Public API endpoints should not be added until the frontend actually needs them.
