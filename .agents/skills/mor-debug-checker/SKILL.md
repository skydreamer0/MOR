---
name: mor-debug-checker
description: Use when debugging MOR pytest failures, runtime errors, broken Flask routes, UI regressions, Excel export problems, or forecast calculation mismatches.
---

# MOR Debug Checker

Work from evidence:

1. Capture the failing command, route, or symptom.
2. Reproduce the issue with the smallest command or test.
3. Trace the relevant data path: route -> service -> model -> template/export.
4. Add a regression test before fixing when behavior should be preserved.
5. Fix only the root cause.
6. Re-run the focused test and any affected broader suite.

Report only:

- Cause.
- Modified files.
- Verification.
- Remaining risk or next step.
