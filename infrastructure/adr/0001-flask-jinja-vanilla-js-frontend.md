# ADR 0001: Frontend Architecture - Flask/Jinja with Vanilla JavaScript

## Status
Accepted

## Context
MOR needs a highly interactive frontend workspace to review thousands of forecast rows, adjust quantities, and exclude specific records before exporting to an Excel workbook. We evaluated whether to introduce a Single Page Application (SPA) framework (like React or Next.js) or maintain the current Server-Side Rendered (SSR) approach.

## Decision
We will use **Flask & Jinja** for the initial page load, and enhance the table with **Vanilla JavaScript** (Airtable / Retool interaction model) to handle searching, filtering, and live state updates.

## Rationale
1. **No Backend Persistence Yet**: The application loads Excel data into memory and outputs Excel. Since there are no complex databases, keeping the state tied to the HTML form DOM is simplest.
2. **Single Operational View**: The tool currently operates on a single screen. A full SPA architecture would introduce unnecessary routing and API overhead.
3. **Form Submission**: Native HTML form submissions map perfectly to the existing `POST /export` flow.
4. **No Build Step**: Using Vanilla JS and CSS avoids adding Node.js, Webpack, or Vite build steps to a simple Python project.

## Consequences
- The JS controller must carefully sync state between the DOM attributes and the visual layer.
- If the application later requires multi-step wizard workflows, saved drafts with edit histories, or real-time multi-user collaboration, we will need to re-evaluate and likely adopt a frontend framework (e.g., React).
