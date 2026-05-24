# Issue tracker: GitHub

Issues and PRDs for this repo are tracked in GitHub Issues.
Use the `gh` CLI for issue operations.

## Repository

- `skydreamer0/MOR`

## Conventions

- Create issue: `gh issue create --title "..." --body "..."`
- Read issue with comments: `gh issue view <number> --comments`
- List issues: `gh issue list --state open`
- Comment: `gh issue comment <number> --body "..."`
- Add/remove labels: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- Close issue: `gh issue close <number> --comment "..."`

## Skill mapping

- When a skill says "publish to the issue tracker", create a GitHub issue.
- When a skill says "fetch the relevant ticket", use `gh issue view <number> --comments`.
