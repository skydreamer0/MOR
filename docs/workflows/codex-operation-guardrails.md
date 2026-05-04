# Codex Operation Guardrails

## Purpose

Use this checklist before Codex changes MOR code, templates, tests, or docs. It keeps work small, avoids repeated tool errors, and makes verification results clear.

## Start Of Task

1. Restate the task in one sentence.
2. List files to inspect or change before editing.
3. Read only active docs in `docs/workflows/` and `infrastructure/` when workflow context is needed.
4. Never read `docs/archive/` or files prefixed with `superseded-` for implementation context.
5. Check `git status --short` and do not touch unrelated user changes.

## File Scope

- Prefer one feature or fix at a time.
- Keep edits in the smallest possible files.
- For MOR code edits, usually inspect only the affected backend module, template, and focused test.
- For UI changes, read `DESIGN.md` and keep the layout compact and table-first.
- Do not overwrite `.xlsx` source files.
- Do not add dependencies without explicit approval.

## PowerShell And Python Commands

Use the verified MOR runtime:

```powershell
D:\AI\python.exe
```

Prefer direct commands over complex inline scripts. If inline Python is needed, use double quotes around the `-c` argument and single quotes inside Python strings:

```powershell
D:\AI\python.exe -c "print('ok')"
```

Avoid PowerShell here-strings piped into Python for quick checks because BOM/encoding can create `U+FEFF` syntax errors.

## Testing

Run the focused test first:

```powershell
D:\AI\python.exe -m pytest tests\test_operational_views.py -q
```

Run the full suite before claiming shared backend or route work is complete:

```powershell
D:\AI\python.exe -m pytest -q
```

If pytest fails during setup with a Windows temp permission error, retry with an explicit base temp:

```powershell
D:\AI\python.exe -m pytest -q --basetemp=C:\tmp\mor-pytest-basetemp
```

If sandboxing blocks that temp directory, rerun the same command with escalation instead of changing the test code.

## Debugging Rules

- Reproduce the issue before fixing it.
- Trace the data path from route or caller to service, model, template, or export.
- For behavior changes, add a focused failing test before production code.
- Fix the root cause only.
- Re-run the focused test, then the affected broader suite.

## Budget Rule

Company budget is authoritative. Dashboard budget totals must come from `budget_targets` for the selected year and month, not from visible forecast rows, sales history, exclusion rules, or product monitor filters.

## Browser And App Checks

For frontend or route changes:

1. Start the app with `D:\AI\python.exe app.py`.
2. Open `http://127.0.0.1:5000/`.
3. Check the affected route only unless the change touches shared layout or scripts.
4. Confirm Chinese labels, numeric alignment, sticky tables, and fixed total/export controls still render correctly.

## Final Report

Keep the final report short:

- Changed files.
- Completed work.
- Verification commands and results.
- Remaining risk.
- Up to 3 next steps.

Mention unrelated dirty files separately and do not imply they were modified by Codex.
