# Active Documentation Index

Use this file to keep AI and human collaborators from reading stale plans by default.

## Read First

- `README.md` — current product and architecture overview.
- `ROADMAP.md` — current work queue and near-term backlog.
- `AGENTS.md` — MOR-specific coding and documentation rules.

## Read By Task

- Backend routes or forecast behavior: `src/backend/*`, `tests/*`, then `infrastructure/project_architecture_and_implementation_plan.md` only if architectural context is needed.
- Database or DB-first request work: `infrastructure/backend/database_schema.md`.
- UI work: `DESIGN.md`, `docs/design/frontend-logic-architecture.md`, and relevant templates/static files.
- Local setup or browser verification: `docs/workflows/local-setup.md`.
- Agent workflow: `docs/workflows/codex-operation-guardrails.md` and `docs/workflows/mor-skills.md`.

## Do Not Read For Implementation Context

- `docs/archive/`
- files prefixed with `superseded-`

Historical implementation plans were moved to `docs/archive/plans/` after their useful decisions were absorbed into the active docs above.
