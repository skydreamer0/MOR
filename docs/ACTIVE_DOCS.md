# Active Documentation Index

Use this file to keep AI and human collaborators from reading stale plans by default.

## Read First

- `README.md` — current product and architecture overview.
- `ROADMAP.md` — current work queue, near-term backlog, and active refactor order.
- `AGENTS.md` — MOR-specific coding and documentation rules.

## Read By Task

- Planning or prioritization: `ROADMAP.md`.
- Backend routes or forecast behavior: `src/backend/*`, `tests/*`, then `docs/architecture/current-architecture.md` only if architectural context is needed.
- Database or DB-first request work: `docs/architecture/database_schema.md`.
- UI work: `DESIGN.md`, `docs/design/ui-design-system-roadmap.md` when changing shared UI structure, and relevant templates/static files.
- UI/UX improvement execution: `docs/design/2026-07-04-frontend-uiux-improvement-roadmap.md` (active WP1–WP6 work packages).
- Local setup or browser verification: `docs/workflows/local-setup.md`.
- Agent workflow: `docs/workflows/codex-operation-guardrails.md` and `docs/workflows/mor-skills.md`.

## Do Not Read For Implementation Context

- `docs/archive/`
- files prefixed with `superseded-`
- old implementation plans not referenced by `ROADMAP.md`

Historical implementation plans and one-off review artifacts are moved to `docs/archive/plans/` after their useful decisions are absorbed into `ROADMAP.md`.
