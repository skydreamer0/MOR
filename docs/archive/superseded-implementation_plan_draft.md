DO NOT USE FOR IMPLEMENTATION

# Master Implementation Plan & Roadmap

## 1. Executive Summary
This document serves as the primary Product Requirements Document (PRD) and Implementation Roadmap for MOR's Forecast Review Tool. The goal is to upgrade the current single-page application into an **Enterprise-Grade "Airtable/Retool-style" Review Workspace**, while maintaining a strict, testable Python/Flask backend.

## 2. Strategic Objectives
- **Data Integrity:** Prevent manual errors by introducing strict validation (e.g. no negative numbers, focus on first error).
- **Enterprise UI Experience:** Shift from a static HTML table to an interactive workspace with live search, filtering, and real-time total recalculations.
- **Architectural Scalability:** Ensure the codebase is clean, decoupled, and prepared for future database integration without breaking current functionalities.

## 3. Phased Roadmap

### Phase 1: Foundation & Stability (Completed)
- ✅ Establish `infrastructure/` documentation structure (PRD, TDD, ADR, DB Schema).
- ✅ Clean up existing Jinja templates and route structures.
- ✅ Implement proper UTF-8 handling to prevent mojibake in Chinese labels.

### Phase 2: Component Decoupling & Asset Extraction (Targeted)
**Goal:** Transition from monolithic HTML files to structured frontend assets.
- Extract all inline CSS to `static/css/mor.css`.
- Implement Design Tokens (CSS Variables) for enterprise color palettes (e.g. `--primary: #2563eb`).
- Extract inline JavaScript to `static/js/forecast_table_controller.js`.
- Establish clear `data-*` attributes for DOM state management.

### Phase 3: The Airtable / Retool Experience
**Goal:** Deliver a highly interactive workspace for operational efficiency.
- **Search & Filter Bar:** Implement a sticky action bar above the table.
- **Client-Side Filtering:** Allow filtering by customer name, product code, and status (`Auto`, `Not-due`, `Edited`, `Excluded`).
- **Live Recalculation:** When quantities are edited or rows are excluded, instantly recalculate row-level `estimated_amount` and the `grand_total` at the bottom bar.
- **Visual Cues:** Highlight edited rows, grey out excluded rows, and flag invalid inputs in red.

### Phase 4: Validation & Error Handling
**Goal:** Prevent bad data from reaching the backend export.
- **Client Validation:** Block non-numeric characters and negative numbers in the browser. Automatically focus the first invalid input on export attempt.
- **Server Validation:** Reinforce client checks in `web/form_parser.py` returning HTTP 400 with a clean error message.

### Phase 5: Future Enhancements (API & Persistence)
**Goal:** Prepare for v2 features.
- Develop JSON presenter `web/forecast_presenter.py`.
- Introduce `GET /api/v1/forecast/preview` for asynchronous calculations.
- Introduce PostgreSQL or SQLite persistence for saving monthly drafts and tracking edit histories.

## 4. Execution Workflow
1. Pick a task from the current active Phase.
2. Write unit tests for Python modules *before* implementing the logic.
3. Keep PRs small, isolated to one task.
4. Ensure `pytest -q` passes before moving to the next task.

