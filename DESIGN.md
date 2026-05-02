# MOR Design System

This file follows the DESIGN.md idea from VoltAgent's awesome-design-md: keep the visual system in plain Markdown so coding agents can preserve a consistent UI.

## 1. Visual Theme & Atmosphere

MOR is an internal sales forecast tool. The interface should feel quiet, operational, and spreadsheet-native. It is not a marketing site and should not use hero sections, decorative illustrations, or large editorial layouts.

The best visual direction is a structured data workspace inspired more by Airtable and enterprise dashboards than consumer SaaS pages:

- Dense but readable tables.
- Calm white and light-gray surfaces.
- Strong numeric alignment.
- Clear status badges for forecast logic.
- Persistent actions for review and export.
- Minimal decoration; every visual element should help scanning, comparison, or correction.

## 2. Color Palette & Roles

Current tokens:

| Token | Hex | Role |
| --- | --- | --- |
| `--ink` | `#16202a` | Primary text |
| `--muted` | `#667085` | Secondary labels and metadata |
| `--line` | `#d9e0e7` | Borders and table dividers |
| `--panel` | `#ffffff` | Cards, table surfaces, fixed bars |
| `--bg` | `#f3f6f8` | Page background |
| `--accent` | `#0f766e` | Primary actions, totals, active status |
| `--accent-2` | `#b45309` | Warning / not-due status |

Recommended additions:

| Token | Hex | Role |
| --- | --- | --- |
| `--success-bg` | `#e7f5ef` | Forecast-in-month badge background |
| `--warning-bg` | `#fff4df` | Not-due badge background |
| `--danger` | `#b42318` | Validation and export errors |
| `--focus` | `#2563eb` | Keyboard focus ring |
| `--surface-subtle` | `#f8fafc` | Hover rows and grouped controls |

## 3. Typography Rules

Use `"Microsoft JhengHei", "Segoe UI", Arial, sans-serif`.

| Element | Size | Weight | Notes |
| --- | --- | --- | --- |
| App title | 22px | 700 | Compact, top-left only |
| Metric value | 22px | 700 | Numeric emphasis |
| Table text | 13px | 400 | Dense data scanning |
| Form controls | 14px | 400/700 | Buttons use 700 |
| Labels | 13px | 400 | Muted color |

Rules:

- Do not scale fonts with viewport width.
- Keep letter spacing at `0`.
- Prefer tabular numeric alignment where available.
- Keep headings compact inside operational screens.

## 4. Component Stylings

### Header

Sticky top bar with title on the left and period controls on the right. It should remain compact and preserve vertical space for the table.

### Metric Summary

Use four metric tiles for target month, shown rows, auto-forecast rows, and current total. Metrics should be visible before the table and should not become decorative cards inside other cards.

### Table

The table is the primary UI. Preserve:

- Sticky header.
- Horizontal scroll for many columns.
- Right-aligned numeric columns.
- No row height shifts when editing quantity.
- Clear excluded row styling.

Future table improvements should add filtering, sorting, and column grouping before adding charts.

### Inputs

Numeric quantity fields should be compact, right-aligned, and stable width. Invalid states should use border plus inline or row-level error text.

### Buttons

Primary actions use `--accent`, white text, 6px radius, and strong weight. Avoid oversized buttons; this is a work tool.

### Status Badges

Use concise labels:

- `本月可能跳單` for auto-in-month rows.
- `未到週期` for rows included for review but not automatically forecast.

Badges should be readable but not dominate the table.

## 5. Layout Principles

- Desktop-first table layout with responsive fallbacks.
- Keep the table and summary in a single review flow.
- Use fixed bottom export bar only for global total and export action.
- Keep spacing in 4px increments: 8, 12, 16, 20, 24.
- Avoid nested cards and marketing-style section bands.

## 6. Depth & Elevation

Use only subtle depth:

- Header: border-bottom, no heavy shadow.
- Table wrapper: border and white surface.
- Bottom bar: light upward shadow to separate from data.

Do not use gradient orbs, blurred blobs, glass effects, or deep shadows.

## 7. Do's and Don'ts

Do:

- Optimize for repeated monthly review.
- Make forecast status, manual override, exclusion, and total impact obvious.
- Keep all currency and quantity values aligned.
- Preserve spreadsheet familiarity.

Don't:

- Turn the first screen into a landing page.
- Hide key data behind cards or modal flows.
- Use visual decoration that competes with the table.
- Use a one-note teal-only palette; add neutral and status roles.

## 8. Responsive Behavior

For narrow screens:

- Stack header controls below the title.
- Collapse metrics to one column.
- Keep the table horizontally scrollable rather than compressing columns until unreadable.
- Maintain 38px or larger touch targets.

## 9. Agent Prompt Guide

When changing MOR UI, use this prompt:

> Build a compact, operational sales forecast workspace. Preserve spreadsheet-like density, sticky table headers, right-aligned numbers, calm neutral surfaces, teal primary actions, and clear forecast status badges. Do not add marketing sections, decorative backgrounds, or oversized hero typography.
