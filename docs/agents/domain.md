# Domain Docs

How engineering skills should consume domain documentation in this repo.

## Layout

This repo is configured as **single-context**.

- Read root `CONTEXT.md` when present.
- Read relevant ADRs in `docs/adr/` when present.
- If these files are missing, proceed without blocking.

## Usage rules

- Prefer glossary/domain terms defined in `CONTEXT.md`.
- If a proposal conflicts with an ADR, call out the conflict explicitly.
- Do not invent alternate domain vocabulary when established terms exist.
