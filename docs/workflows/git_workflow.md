# Version Control & Development Standards

## 1. Branching Strategy
MOR uses a standard feature-branching workflow.
- `main` : Stable, production-ready code.
- `feat/*` : New features (e.g. `feat/airtable-grid`).
- `fix/*` : Bug fixes.
- `refactor/*`: Architecture or code structure changes.

*Note: Since MOR is local-first, trunk-based development directly on main is acceptable for solo developers as long as commits follow the convention.*

## 2. Commit Message Convention
We strictly follow Conventional Commits: `<type>(<scope>): <subject>`

**Types:**
- `feat`: A new feature (e.g., `feat(ui): add Airtable style table filters`)
- `fix`: A bug fix (e.g., `fix(export): resolve excel crash with empty rows`)
- `docs`: Documentation only changes (e.g., `docs(arch): update system architecture`)
- `refactor`: A code change that neither fixes a bug nor adds a feature
- `test`: Adding missing tests or correcting existing tests

## 3. Pull Request / Code Review Rules
- **Testing:** No PR can be merged without passing tests (`pytest -q`).
- **Context:** Every PR must include a description linking to the specific phase of the Implementation Plan.
- **Documentation:** If the PR changes domain boundaries or APIs, the `infrastructure/` documentation MUST be updated simultaneously.

## 4. Coding Standards
- **Python:** Use Type Hints (`-> list[dict]`, `: str`). Ensure variables are `snake_case`.
- **Frontend CSS:** Vanilla CSS using `BEM` or clear semantic classes. Avoid inline styles.
- **Frontend JS:** `camelCase` for variables and functions. `PascalCase` for classes/components.
- **File Encoding:** UTF-8 is mandatory for all `.py`, `.html`, and `.md` files to ensure Chinese characters do not render as mojibake.
