# MOR Agent Instructions

## Fast Codex Workflow

Default response style for MOR work:

1. Keep answers short.
2. Read only the necessary active docs and core files before editing.
3. Before edits, list the files that will be inspected or changed.
4. Handle one feature or fix at a time.
5. Avoid broad refactors unless explicitly requested.
6. Do not repeat known project background.
7. Prefer diff summaries over long explanations.
8. After edits, run the relevant test or syntax check.
9. Final reports should include changed files, completed work, verification, risk, and up to 3 next steps.

Reusable prompt for small tasks:

```text
請用最少 token 完成以下任務。

任務：
[貼需求]

限制：
1. 先不要改檔，先列出你會檢查哪些檔案。
2. 只讀必要檔案。
3. 不要重複說明背景。
4. 不要大改架構。
5. 修改完成後跑測試。
6. 最後只回報：
   A. 修改檔案
   B. 完成內容
   C. 驗證結果
   D. 下一步
```

Quick development loop:

1. Analyze one small task.
2. Confirm direction or file scope.
3. Edit only scoped files.
4. Run tests or syntax checks.
5. Review `git diff`.
6. Prepare a concise commit message.

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
D:\AI\python.exe -m py_compile app.py src\backend\app.py src\backend\sales_forecast.py src\backend\forecast_config.py src\backend\forecast_models.py src\backend\data_loader.py src\backend\forecast_engine.py src\backend\forecast_workbench_context.py src\backend\forecast_page_context.py src\backend\dashboard_metrics.py src\backend\data_health_summary.py src\backend\monthly_review_context.py src\backend\settings_context.py src\backend\exporter.py src\backend\web\form_parser.py src\backend\web\forecast_presenter.py
```

## Project Structure

Current intended structure:

```text
app.py                         Flask app launch wrapper
ROADMAP.md                     Small-task roadmap and priority queue
src/backend/                   Canonical backend logic
  app.py                       Flask app and route wiring
  forecast_config.py           Centralized file names, sheets, columns, limits
  forecast_models.py           ForecastTarget, ForecastRow, ForecastSummary
  data_loader.py               Excel loading and DataFrame normalization
  forecast_engine.py           Forecast calculation and adjustments
  analytics.py                 Analytics slices and dashboard risk/status helpers
  dashboard_metrics.py         Dashboard KPI metrics
  data_health_summary.py       Data health summary model/builder
  forecast_page_context.py     Forecast page render context
  monthly_review_context.py    Monthly Review page/export context
  settings_context.py          Settings page context
  exporter.py                  Excel workbook export
  sales_forecast.py            Compatibility facade for older imports
  web/form_parser.py           Form parsing and validation
  web/forecast_presenter.py    Grid presentation
templates/index.html           Dashboard
templates/forecast.html        Forecast adjustment and export UI
templates/product_monitor.html Product drop monitor
templates/settings.html        Settings and data checks
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
- For frontend design-system guidance, read `DESIGN.md` and `docs/design/ui-design-system-roadmap.md`.
- For local setup and browser verification, read `docs/workflows/local-setup.md`.

## Documentation Rules

Update documentation when changing:

- User-visible workflows.
- Forecast calculation rules.
- Excel input/output shape.
- Frontend structure or design tokens.
- Agent workflow or testing instructions.

Use concise Markdown. Prefer diagrams only when they clarify flow or ownership.
**IMPORTANT:** Codex and AI subagents MUST ONLY read active docs in `docs/architecture/`, `docs/adr/`, `docs/design/`, and `docs/workflows/`. They MUST NEVER read files in `docs/archive/` or any file prefixed with `superseded-` for implementation context.

For MOR-specific prompt and skill workflows, see:

- `ROADMAP.md`
- `docs/workflows/codex-prompt-workflow.md`
- `docs/workflows/mor-skills.md`

## Skill Selection Rules

Before starting non-trivial work, decide which skills apply and state them briefly.

- Use the smallest useful skill set for the task.
- Prefer MOR-specific skills when they fit: `mor-roadmap-planner`, `mor-code-editor`, or `mor-debug-checker`.
- Add general engineering skills only when they change the workflow, such as TDD, debugging, planning, code review, or frontend design.
- If no skill applies, say so briefly and continue with the normal MOR workflow.
- Do not read archived or superseded docs while deciding skills.

## Subagent Rules

Use subagents when a task has separable investigation or implementation tracks and the extra context cost is justified.

- Prefer subagents for broad audits, noisy bug hunts, multi-area roadmap execution, or independent test/design/doc reviews.
- Do not use subagents for small single-file edits, simple questions, or tasks where one agent can safely inspect and patch the relevant files.
- If the user explicitly asks for subagents or parallel agents, use them unless the task is too small to benefit.
- The main agent must choose the needed skills first, assign each subagent a narrow role, and integrate the final decision.

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

## Agent skills

### Issue tracker

Issues are tracked in GitHub Issues for this repository (`skydreamer0/MOR`). See `docs/agents/issue-tracker.md`.

### Triage labels

Triage uses the default five-label vocabulary (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

This repo is configured as single-context; use root `CONTEXT.md` (when present) and `docs/adr/`. See `docs/agents/domain.md`.
