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

All tokens are defined in `static/css/mor.css` `:root`. Edit values there; this table is the reference.

**Neutral**

| Token | Hex | Role |
| --- | --- | --- |
| `--ink` | `#0f172a` | Primary text |
| `--ink-secondary` | `#1e293b` | Secondary headings |
| `--muted` | `#64748b` | Labels and metadata |
| `--muted-light` | `#94a3b8` | Placeholder, disabled text |
| `--line` | `#e2e8f0` | Borders and table dividers |
| `--line-subtle` | `#f1f5f9` | Subtle dividers |
| `--panel` | `#ffffff` | Cards, table surfaces, fixed bars |
| `--bg` | `#f8fafc` | Page background |
| `--surface-subtle` | `#f1f5f9` | Hover rows, grouped controls |
| `--surface-elevated` | `#ffffff` | Elevated panels |

**Brand — Teal**

| Token | Hex | Role |
| --- | --- | --- |
| `--accent` | `#0d9488` | Primary actions, active state |
| `--accent-hover` | `#0f766e` | Button hover |
| `--accent-active` | `#115e59` | Button active / pressed |
| `--accent-subtle` | `rgba(13,148,136,0.08)` | Tint backgrounds, nav hover |
| `--accent-ring` | `rgba(13,148,136,0.25)` | Focus ring glow |
| `--accent-2` | `#d97706` | Warning / not-due status |

**Semantic**

| Token | Hex | Role |
| --- | --- | --- |
| `--danger` | `#dc2626` | Errors, destructive actions |
| `--danger-hover` | `#b91c1c` | Danger button hover |
| `--danger-bg` | `#fef2f2` | Error backgrounds |
| `--danger-border` | `#fca5a5` | Error borders |
| `--success-bg` | `#ecfdf5` | Success backgrounds, badge bg |
| `--success-text` | `#047857` | Success text, positive values |
| `--success-border` | `#a7f3d0` | Success borders |
| `--warning-bg` | `#fffbeb` | Warning backgrounds |
| `--warning-text` | `#92400e` | Warning text |
| `--warning-border` | `#fde68a` | Warning borders |
| `--focus` | `#38bdf8` | Keyboard focus ring color |
| `--focus-ring` | `rgba(56,189,248,0.25)` | Focus ring glow |

**Interactive Row States**

| Token | Hex | Role |
| --- | --- | --- |
| `--row-hover` | `#eef6ff` | Table row hover background |
| `--row-active` | `#e0f0ff` | Row with detail panel open |

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
- Do not load external web fonts for the main UI; use the local/system stack above.
- Keep letter spacing at `0`.
- Prefer tabular numeric alignment where available.
- Keep headings compact inside operational screens.

## 3.1 Control Size Rules

Control size tokens live in `static/css/mor.css` and should be reused instead of one-off heights.

| Token | Size | Role |
| --- | --- | --- |
| `--control-h` | `32px` | Normal inputs, selects, and primary buttons |
| `--control-compact-h` | `28px` | Toolbar buttons, segmented controls, and compact tags |
| `--control-nav-h` | `28px` | Header navigation action button |
| `--control-icon-size` | `28px` | Icon-only and short inline action buttons |

## 4. Component Stylings

### Header

Sticky top bar with title on the left and period controls on the right. It should remain compact and preserve vertical space for the table. Primary tabs should stay limited to 工作台 and 品項管理; product exclusion is configured inside 品項管理 rather than a separate page.

### Page Toolbars

Forecast, monitor, and settings workbars should use the shared `workbench-toolbar` structure with `toolbar-title`, `toolbar-controls`, and `toolbar-actions` regions. Page-specific classes may remain for width or behavior hooks, but the layout rhythm and control spacing should come from the shared toolbar rules.

### Dashboard Layout

The dashboard follows a three-zone information hierarchy: **Status → Risk → Action**.

**Zone 1 — Progress Hero:** A single card showing budget target, forecast amount, a visual progress bar with conditional coloring (green ≥100%, amber 90-99%, red <90%), remaining days in the month, and four sub-metrics (actual, forecast delta, GAP, risk counts). This replaces the old flat metric tiles.

**Zone 2 — Risk Dashboard:** A two-column layout. Left panel shows status distribution (high risk, slight decline, normal/growth, no history) with color-coded dot indicators. Right panel shows the top-5 customer risk ranking with inline bar charts sorted by GAP amount.

**Zone 3 — High-Risk Detail:** A compact table of high-risk items sorted by amount impact (largest negative first), with columns for quantity diff, amount impact, status badge, and an inline jump link to the forecast adjustment page.

**Data Health Alert:** Shown as a warning banner only when data issues exist (missing budget rows or zero-price rows). Does not appear on a clean dashboard. Full health details remain on the Settings page.

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

Use 700 weight for button labels. Toolbar actions should use the compact control token instead of page-specific `!important` overrides. Icon buttons should keep a stable square footprint so restore/delete/close controls do not shift table or drawer layout.

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
