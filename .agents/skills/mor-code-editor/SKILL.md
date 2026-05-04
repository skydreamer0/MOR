---
name: mor-code-editor
description: Use when making scoped MOR code or template edits after the task and affected feature area are known.
---

# MOR Code Editor

Before edits:

1. List files to inspect or change.
2. Read only those files plus `AGENTS.md`, `README.md`, and `ROADMAP.md` when needed.
3. Add or update focused tests first for behavior changes.

During edits:

- Keep Flask routes thin.
- Put reusable calculations in backend services.
- Preserve compact operational UI and Chinese labels.
- Avoid unrelated refactors.

After edits:

- Run focused tests.
- Run full tests when routes, shared services, or templates changed.
- Report modified files, diff summary, verification, risk, and up to 3 next steps.
