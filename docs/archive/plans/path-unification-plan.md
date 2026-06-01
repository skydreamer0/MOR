# MOR Path Unification Plan

## 1. Decision

MOR will use one canonical application path:

```text
src/backend/
```

All runtime backend code should live under `src/backend/`.

Root-level Python files should only remain as thin compatibility entrypoints when needed.

## 2. Goal

Unify duplicated backend modules and prevent developers or agents from editing the wrong file.

Current risk:

```text
root/
  app.py
  forecast_engine.py
  data_loader.py
  exporter.py

src/backend/
  engine.py
  loader.py
  exporter.py
```

This creates ambiguity.

Target state:

```text
MOR/
  src/
    backend/
      app.py
      forecast_config.py
      forecast_models.py
      data_loader.py
      forecast_engine.py
      exporter.py
      sales_forecast.py

      web/
        form_parser.py
        forecast_presenter.py

  templates/
    index.html

  static/
    css/
      mor.css
    js/
      forecast-table.js

  tests/
    test_app.py
    test_forecast_engine.py
    test_form_parser.py
    test_exporter.py

  docs/
    architecture/
    design/
    roadmaps/
    plans/
    workflows/
    verification/

  app.py
  requirements.txt
  README.md
```

## 3. Big-company style rule

Large engineering teams usually define one source of truth for each concern.

| Concern                | Canonical location   |
| ---------------------- | -------------------- |
| Runtime backend code   | `src/backend/`       |
| Web form parsing       | `src/backend/web/`   |
| HTML templates         | `templates/`         |
| Static frontend assets | `static/`            |
| Tests                  | `tests/`             |
| Design docs            | `docs/design/`       |
| Architecture docs      | `docs/architecture/` |
| Roadmaps               | `docs/roadmaps/`     |
| Implementation plans   | `docs/plans/`        |
| Verification records   | `docs/verification/` |
| Archived docs          | `docs/archive/`      |

## 4. Compatibility rule

Keep root `app.py` as a launch wrapper only.

```python
from src.backend.app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
```

Root `app.py` should not contain business logic.

## 5. Migration order

### Step 1: Freeze current baseline

Run:

```powershell
D:\AI\python.exe -m pytest -q
D:\AI\python.exe -m py_compile app.py sales_forecast.py forecast_config.py forecast_models.py data_loader.py forecast_engine.py exporter.py web\form_parser.py
git status
git diff
```

Commit current working baseline:

```powershell
git commit -m "chore(baseline): freeze verified forecast review state"
```

### Step 2: Create canonical package

Create:

```text
src/
  __init__.py
  backend/
    __init__.py
    web/
      __init__.py
```

Move backend files into `src/backend/`:

```text
forecast_config.py
forecast_models.py
data_loader.py
forecast_engine.py
exporter.py
sales_forecast.py
```

Move:

```text
web/form_parser.py
web/forecast_presenter.py
```

to:

```text
src/backend/web/
```

### Step 2.1: Preserve Flask template/static paths

Because the Flask application factory will move into `src/backend/app.py`, Flask must be configured to keep using the root-level `templates/` and `static/` directories.

Use:

```python
from pathlib import Path
from flask import Flask

PROJECT_ROOT = Path(__file__).resolve().parents[2]

def create_app(config=None):
    app = Flask(
        __name__,
        template_folder=str(PROJECT_ROOT / "templates"),
        static_folder=str(PROJECT_ROOT / "static"),
    )
    return app
```

Do not move `templates/` or `static/` into `src/backend/` during this migration.
```

### Step 3: Rename only if necessary

Do not rename modules during the first move.

Keep names stable:

```text
forecast_engine.py
data_loader.py
exporter.py
forecast_models.py
```

Avoid switching to shorter names like:

```text
engine.py
loader.py
```

Reason:

Existing test names and docs already reference the current explicit names.

### Step 4: Update imports

Change imports from:

```python
from forecast_engine import ...
from data_loader import ...
from web.form_parser import ...
```

to:

```python
from src.backend.forecast_engine import ...
from src.backend.data_loader import ...
from src.backend.web.form_parser import ...
```

### Step 5: Update tests

Tests should import from canonical path only:

```python
from src.backend.forecast_engine import build_forecast
from src.backend.web.form_parser import parse_export_form
```

No test should import root-level backend modules.

### Step 6: Keep root app.py only

Root `app.py` remains only for local launch.

All actual app logic moves to:

```text
src/backend/app.py
```

### Step 7: Delete duplicate modules

Before deleting, verify no imports still point to the old paths:

```powershell
Select-String -Path *.py,tests\*.py,src\backend\*.py,src\backend\web\*.py -Pattern "from forecast_|import forecast_|from data_loader|import data_loader|from exporter|import exporter|from web\."
```

If any matches are found, fix the imports first.

After verification, delete old root duplicates:

```text
forecast_config.py
forecast_models.py
data_loader.py
forecast_engine.py
exporter.py
sales_forecast.py
web/
```

Keep only:

```text
app.py
```

as launch wrapper.

### Step 8: Update documentation

Update these docs:

```text
docs/architecture/current-architecture.md
docs/design/backend-design.md
docs/workflows/codex-workflow.md
local-setup.md or docs/workflows/local-setup.md
README.md
```

All docs should point to:

```text
src/backend/
```

## 6. Verification checklist

After migration, run:

```powershell
D:\AI\python.exe -m pytest -q
D:\AI\python.exe -m py_compile app.py src\backend\app.py src\backend\sales_forecast.py src\backend\forecast_config.py src\backend\forecast_models.py src\backend\data_loader.py src\backend\forecast_engine.py src\backend\exporter.py src\backend\web\form_parser.py src\backend\web\forecast_presenter.py
D:\AI\python.exe app.py
```

Browser check:

```text
http://127.0.0.1:5000/
```

Verify:

```text
1. 首頁可以開啟
2. 中文標籤正常
3. 預估表格正常
4. manual quantity 可調整
5. exclude 可排除
6. grand total 正確
7. export Excel 成功
8. pytest 全部通過
```

## 7. Guardrails for Codex

Before editing code, Codex must read:

```text
docs/architecture/current-architecture.md
docs/design/backend-design.md
docs/design/data-contract.md
docs/design/forecast-logic.md
docs/architecture/path-unification-plan.md
```

Codex must not edit deprecated root-level duplicates.

If duplicate files exist, canonical priority is:

```text
src/backend/ > root-level files
```

## 8. Commit strategy

Use small commits:

```powershell
git commit -m "refactor(paths): create canonical backend package"
git commit -m "refactor(imports): update backend imports to src package"
git commit -m "test(paths): update tests for canonical backend imports"
git commit -m "docs(paths): document MOR path unification"
git commit -m "chore(paths): remove duplicate root backend modules"
```

## 9. Final target principle

One file should have one owner.

One module should exist in one canonical path.

One document should define one concern.

One command should run the app.

One test command should validate the system.
