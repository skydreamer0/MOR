# MOR Agent Instructions

## Project Context

MOR is a local Flask-based sales forecast tool. It reads Excel sales detail files, estimates monthly customer/product demand, lets the user manually override quantities or exclude rows, and exports the final forecast workbook.

This is an operational data tool, not a marketing site. Preserve spreadsheet-like density, clear numeric alignment, and predictable workflows.

## Setup Commands

Preferred local runtime:

```powershell
D:\AI\python.exe -m pip install -r requirements.txt
D:\AI\python.exe -m pytest -q
D:\AI\python.exe app.py
```

Bundled Codex runtime may also be used for syntax checks:

```powershell
& 'C:\Users\User\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m py_compile app.py src\backend\app.py
```

If dependencies are missing, install from `requirements.txt`. Do not add new third-party dependencies without approval. See `docs/workflows/local-setup.md` for the full setup workflow.

## Test Commands

Run before claiming backend or route work is complete:

```powershell
D:\AI\python.exe -m pytest -q
```

For quick import/syntax validation:

```powershell
D:\AI\python.exe -m py_compile app.py src\backend\app.py src\backend\sales_forecast.py src\backend\forecast_config.py src\backend\forecast_models.py src\backend\data_loader.py src\backend\forecast_engine.py src\backend\exporter.py src\backend\web\form_parser.py src\backend\web\forecast_presenter.py
```

## Project Structure

Current intended structure:

```text
app.py                         Flask app launch wrapper
src/backend/                   Canonical backend logic
  app.py                       Flask app and route wiring
  forecast_config.py           Centralized file names, sheets, columns, limits
  forecast_models.py           ForecastTarget, ForecastRow, ForecastSummary
  data_loader.py               Excel loading and DataFrame normalization
  forecast_engine.py           Forecast calculation and adjustments
  exporter.py                  Excel workbook export
  sales_forecast.py            Compatibility facade for older imports
  web/form_parser.py           Form parsing and validation
  web/forecast_presenter.py    Grid presentation
templates/index.html           Server-rendered forecast review UI
tests/                         Unit and route tests
docs/architecture/             Architecture docs
docs/design/                   Frontend/backend/design-system docs
docs/workflows/                Codex workflow docs
requirements.txt               Python dependency list
```

## Code Rules

- Keep Flask routes thin. Route functions should orchestrate, not contain forecast math.
- Keep forecast logic deterministic and testable without Flask.
- Keep Excel schema details centralized in config or loader modules.
- Preserve Chinese workbook labels and exported sheet names unless the user asks to change them.
- Use UTF-8 for source files and Markdown.
- Do not introduce a frontend framework unless table interactions clearly outgrow Jinja plus small vanilla JavaScript modules.
- Do not add database persistence until monthly version history is explicitly requested.
- Avoid broad refactors unrelated to the current request.

## Design Rules

- Read `DESIGN.md` before changing UI.
- Keep the UI compact, operational, and table-first.
- Do not create landing pages, hero sections, decorative gradients, or marketing-style cards.
- Preserve sticky table headers, right-aligned numbers, clear status badges, and the fixed export/total bar.
- For frontend architecture guidance, read `docs/design/frontend-logic-architecture.md`.
- For local setup and browser verification, read `docs/workflows/local-setup.md`.

## Documentation Rules

Update documentation when changing:

- User-visible workflows.
- Forecast calculation rules.
- Excel input/output shape.
- Frontend structure or design tokens.
- Agent workflow or testing instructions.

Use concise Markdown. Prefer diagrams only when they clarify flow or ownership.
**IMPORTANT:** Codex and AI subagents MUST ONLY read active docs in `infrastructure/` and `docs/workflows/`. They MUST NEVER read files in `docs/archive/` or any file prefixed with `superseded-` for implementation context.

## Subagent Rules

Use subagents only when the user explicitly asks for parallel agents or when a large task clearly benefits from independent exploration and the user has approved that approach.

Good MOR subagent roles:

- Codebase Explorer: current structure, ownership, data flow.
- Bug Hunter: runtime errors, edge cases, encoding issues, Excel failures.
- Test Writer: coverage gaps and required regression tests.
- Refactor Planner: module boundaries and migration sequence.
- Docs Updater: stale README/design/architecture docs.

Each subagent should return:

- Key findings.
- Relevant files.
- Suggested actions.
- Risk level.

The main agent owns final decisions, integration, and the final response.

## Large Task Workflow

For medium or large changes:

1. Inspect related files first.
2. If the task is exploratory or noisy, propose or use subagents when explicitly requested.
3. Summarize findings into immediate fixes, medium-priority improvements, optional cleanup, and recommended order.
4. Write or update design/planning docs before broad implementation.
5. Implement in small verified batches.
6. Run tests and report exact verification performed.

## Safety Rules

- Never revert user changes unless explicitly requested.
- Never run destructive git commands without explicit approval.
- Treat `.xlsx` files as source data; do not overwrite them unless explicitly requested.
- If a generated dependency folder such as `.vendor/` exists, do not include it in architecture docs or commits unless the user asks.
