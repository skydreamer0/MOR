# MOR Forecast Logic

## Purpose

This document defines the calculation rules for the forecast engine. It exists so the forecast quantity logic stays deterministic and does not get reinterpreted in later refactors.

## Core Inputs

Each forecast row is built from historical sales records for one customer and product combination.

The engine should consider:

- Historical sales quantity.
- Historical sales dates.
- Latest unit price.
- Same-month history.
- Recent sales cadence.

## Calculation Rules

### 1. Customer/product grouping

Rows are grouped by customer and product identity.

### 2. Cycle days

`cycle_days` should be derived from the interval between recent order dates in the historical window.

If there are multiple usable intervals, prefer the median or another stable central value over a single outlier.

If there is not enough history to compute a cycle reliably, leave the field blank or use a clearly documented fallback.

### 3. Latest price

`latest_price` should come from the most recent usable historical record for the row.

If multiple records share the latest date, use a deterministic tie-break rule.

### 4. Forecast quantity

`forecast_quantity` is the system estimate before manual override.

The engine should derive it from the row's historical cadence and recent quantity history, not from the user-facing export state.

The exact formula must be stable and test-covered. If the formula changes, update this document first.

### 5. Same-month history

`last_year_same_month_qty` and `this_year_same_month_qty` are supporting signals for seasonal behavior.

Use them as inputs to the forecast basis or review hints, but do not let them silently change the exported review state after the user has reviewed the row.

### 6. No historical data

If a row has too little history:

- Keep the row visible if it is part of the review set.
- Use a documented fallback quantity rule or a zero-like baseline.
- Flag the row so the user can review it explicitly.

### 7. Large or abnormal orders

If a row contains unusually large single orders or other obvious anomalies, the engine should surface them in the basis or status metadata rather than hiding the reason.

### 8. Manual override

Manual quantity always overrides the system quantity at export time when a valid manual value is submitted.

Blank manual quantity means use the system forecast quantity.

### 9. Exclusion

Excluded rows export with zero quantity and zero amount, while still remaining visible in the review UI.

### 10. Export authority

Export must use the submitted reviewed state, not a fresh recomputation that ignores the user's edits.

The backend may validate the state, normalize the payload, and write the workbook.

It must not silently replace a reviewed quantity with a new baseline forecast during export.
