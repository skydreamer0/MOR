# MOR Skills

These repo-local skills document repeatable MOR workflows. They can be copied into the active Codex skills directory if global discovery is needed.

## mor-roadmap-planner

Use for turning broad MOR requests into small roadmap tasks.

Expected output:

- Goal.
- Small task breakdown.
- Priority order.
- Files or docs likely affected.
- Verification needed.

## mor-code-editor

Use for scoped MOR code edits after a task is chosen.

Expected workflow:

- List files to inspect/change.
- Read only necessary files.
- Add or update focused tests first when behavior changes.
- Edit scoped files only.
- Run focused tests.
- Report diff summary.

## mor-debug-checker

Use for MOR test failures, runtime errors, broken UI behavior, and suspicious calculation results.

Expected workflow:

- Capture the failing command or symptom.
- Identify the smallest reproduction.
- Trace the relevant route/service/template/data flow.
- Add a regression test before the fix when feasible.
- Run focused verification and then broader tests if touched code is shared.
