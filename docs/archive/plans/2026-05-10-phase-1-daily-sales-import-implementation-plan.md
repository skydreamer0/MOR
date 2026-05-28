# Phase 1 Daily Sales Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first working slice for importing a current-month cumulative sales workbook into SQLite and showing that imported current-month actual quantity on the product monitor page.

**Architecture:** Keep the import flow isolated from the forecast engine. Add dedicated daily sales tables, a focused importer module, and a small product-monitor integration that reads daily actuals only for the selected month. Do not change the forecast adjustment/export workflow in Phase 1.

**Tech Stack:** Flask, Jinja, SQLite, pandas/openpyxl, pytest.

---

## Scope

In scope:

- Add DB tables for import batches and current-month daily sales actuals.
- Normalize the daily sales workbook format by column names, not file name.
- Treat each imported workbook as the latest complete monthly snapshot.
- Ignore summary/incomplete rows.
- Use `銷售數量 + 贈品數量` as actual quantity.
- Store `含稅淨額` as the current reliable amount field.
- Store `折後業績` as `bonus_basis_amount`, but do not use it in calculations or UI.
- Add product monitor upload UI and import route.
- Let product monitor current-month quantity prefer imported daily actuals when available.

Out of scope:

- Workday calendar.
- Product-frequency month-end projection.
- Expanded product monitor v2 table layout.
- Month close.
- Monthly review page.
- Dashboard and forecast page DB-first migration.

## File Map

- Modify `src/backend/database.py`
  - Add `daily_import_batches` and `daily_sales_actuals`.
  - Add safe migrations/indexes.

- Create `src/backend/daily_sales_importer.py`
  - Normalize daily workbook rows.
  - Validate required columns.
  - Import a workbook transactionally.
  - Fetch monthly daily-actual aggregates for product monitor.

- Modify `src/backend/operational_views.py`
  - Add optional daily actual lookup when building monitor rows.
  - Keep dashboard metrics unchanged in Phase 1.

- Modify `src/backend/app.py`
  - Add `POST /monitor/products/import`.
  - Pass import result messages into `product_monitor.html`.
  - Clear context cache after successful import.

- Modify `templates/product_monitor.html`
  - Add compact upload form above the monitor table.
  - Display import success/error message.

- Create `tests/test_daily_sales_importer.py`
  - Unit tests for normalization, ignored summary rows, same-month validation, DB overwrite behavior, and aggregate query.

- Modify `tests/test_app.py`
  - Route/template tests for upload UI and import POST behavior.

## Data Contracts

Required input columns:

```text
出貨日期
客戶代號
客戶簡稱
產品
產品簡稱
銷售數量
贈品數量
銷貨淨價
含稅淨額
折後業績
發票編號
出貨單號
單別
業績屬性
```

Rows are valid only when these fields are usable:

```text
出貨日期
客戶簡稱
產品
```

Computed fields:

```text
actual_quantity = 銷售數量 + 贈品數量
taxed_amount = 含稅淨額
bonus_basis_amount = 折後業績
```

Same-month rule:

```text
All valid detail rows in one import must belong to the same year/month.
```

Overwrite rule:

```text
DELETE FROM daily_sales_actuals WHERE sales_year = ? AND sales_month = ?
INSERT all valid rows from the latest import
```

## Task 1: Add Database Tables

**Files:**
- Modify: `src/backend/database.py`
- Test: `tests/test_daily_sales_importer.py`

- [ ] **Step 1: Write failing DB schema test**

Create `tests/test_daily_sales_importer.py` with a schema test:

```python
from pathlib import Path

from src.backend.database import MORDatabase


def test_daily_sales_tables_are_initialized(tmp_path: Path):
    db = MORDatabase(tmp_path / "mor_workbench.db")

    with db.get_connection() as conn:
        batch_cols = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(daily_import_batches)").fetchall()
        }
        actual_cols = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(daily_sales_actuals)").fetchall()
        }

    assert {
        "id",
        "source_filename",
        "source_hash",
        "sales_year",
        "sales_month",
        "imported_at",
        "row_count",
        "date_start",
        "date_end",
        "quantity_total",
        "taxed_amount_total",
        "status",
        "message",
    }.issubset(batch_cols)
    assert {
        "id",
        "sales_year",
        "sales_month",
        "sales_date",
        "customer_code",
        "customer_name",
        "product_code",
        "product_name",
        "sales_quantity",
        "gift_quantity",
        "actual_quantity",
        "net_unit_price",
        "taxed_amount",
        "bonus_basis_amount",
        "invoice_number",
        "shipment_number",
        "order_type",
        "performance_type",
        "import_batch_id",
    }.issubset(actual_cols)
```

- [ ] **Step 2: Run failing test**

Run:

```bash
python -m pytest -q tests/test_daily_sales_importer.py::test_daily_sales_tables_are_initialized
```

Expected: FAIL because the new tables do not exist.

- [ ] **Step 3: Add tables and migrations**

In `src/backend/database.py`, add after `sales_records` initialization:

```python
conn.execute("""
    CREATE TABLE IF NOT EXISTS daily_import_batches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_filename TEXT NOT NULL,
        source_hash TEXT NOT NULL,
        sales_year INTEGER NOT NULL,
        sales_month INTEGER NOT NULL,
        imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        row_count INTEGER DEFAULT 0,
        date_start DATE,
        date_end DATE,
        quantity_total REAL DEFAULT 0,
        taxed_amount_total REAL DEFAULT 0,
        status TEXT DEFAULT 'success',
        message TEXT
    )
""")
conn.execute("""
    CREATE TABLE IF NOT EXISTS daily_sales_actuals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sales_year INTEGER NOT NULL,
        sales_month INTEGER NOT NULL,
        sales_date DATE NOT NULL,
        customer_code TEXT,
        customer_name TEXT NOT NULL,
        product_code TEXT NOT NULL,
        product_name TEXT,
        sales_quantity REAL DEFAULT 0,
        gift_quantity REAL DEFAULT 0,
        actual_quantity REAL DEFAULT 0,
        net_unit_price REAL DEFAULT 0,
        taxed_amount REAL DEFAULT 0,
        bonus_basis_amount REAL DEFAULT 0,
        invoice_number TEXT,
        shipment_number TEXT,
        order_type TEXT,
        performance_type TEXT,
        import_batch_id INTEGER,
        FOREIGN KEY (import_batch_id) REFERENCES daily_import_batches(id)
    )
""")
conn.execute("CREATE INDEX IF NOT EXISTS idx_daily_actuals_month ON daily_sales_actuals(sales_year, sales_month)")
conn.execute("CREATE INDEX IF NOT EXISTS idx_daily_actuals_row ON daily_sales_actuals(customer_name, product_code)")
```

- [ ] **Step 4: Run schema test**

Run:

```bash
python -m pytest -q tests/test_daily_sales_importer.py::test_daily_sales_tables_are_initialized
```

Expected: PASS.

## Task 2: Normalize Daily Sales Rows

**Files:**
- Create: `src/backend/daily_sales_importer.py`
- Modify: `tests/test_daily_sales_importer.py`

- [ ] **Step 1: Write failing normalization test**

Append:

```python
import pandas as pd

from src.backend.daily_sales_importer import normalize_daily_sales


def test_normalize_daily_sales_ignores_summary_rows_and_computes_quantity():
    raw = pd.DataFrame(
        [
            {
                "出貨日期": "2026-05-04",
                "客戶代號": "HIN231001R",
                "客戶簡稱": "耕莘台北",
                "產品": "T5EL1",
                "產品簡稱": "ELI 22.5癌立佳",
                "銷售數量": 5,
                "贈品數量": 1,
                "銷貨淨價": 5309.2,
                "含稅淨額": 26546,
                "折後業績": 25282,
                "發票編號": "BC59676516",
                "出貨單號": "1A8101934077",
                "單別": "正常銷",
                "業績屬性": "處方",
            },
            {
                "出貨日期": None,
                "客戶代號": None,
                "客戶簡稱": None,
                "產品": None,
                "產品簡稱": "每日總計",
                "銷售數量": 999,
                "贈品數量": 0,
                "銷貨淨價": 0,
                "含稅淨額": 999,
                "折後業績": 999,
                "發票編號": None,
                "出貨單號": None,
                "單別": None,
                "業績屬性": None,
            },
        ]
    )

    rows = normalize_daily_sales(raw)

    assert len(rows) == 1
    row = rows.iloc[0]
    assert row.sales_year == 2026
    assert row.sales_month == 5
    assert row.customer_name == "耕莘台北"
    assert row.product_code == "T5EL1"
    assert row.actual_quantity == 6
    assert row.taxed_amount == 26546
    assert row.bonus_basis_amount == 25282
```

- [ ] **Step 2: Run failing test**

Run:

```bash
python -m pytest -q tests/test_daily_sales_importer.py::test_normalize_daily_sales_ignores_summary_rows_and_computes_quantity
```

Expected: FAIL because `daily_sales_importer.py` does not exist.

- [ ] **Step 3: Implement normalizer**

Create `src/backend/daily_sales_importer.py`:

```python
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

import pandas as pd

from src.backend.data_loader import normalize_product_code
from src.backend.database import MORDatabase


DAILY_SALES_COLUMNS = {
    "sales_date": "出貨日期",
    "customer_code": "客戶代號",
    "customer_name": "客戶簡稱",
    "product_code": "產品",
    "product_name": "產品簡稱",
    "sales_quantity": "銷售數量",
    "gift_quantity": "贈品數量",
    "net_unit_price": "銷貨淨價",
    "taxed_amount": "含稅淨額",
    "bonus_basis_amount": "折後業績",
    "invoice_number": "發票編號",
    "shipment_number": "出貨單號",
    "order_type": "單別",
    "performance_type": "業績屬性",
}


@dataclass(frozen=True)
class DailySalesImportResult:
    batch_id: int
    sales_year: int
    sales_month: int
    row_count: int
    date_start: object
    date_end: object
    quantity_total: float
    taxed_amount_total: float


@dataclass(frozen=True)
class DailyActualAggregate:
    actual_quantity: float
    taxed_amount: float
    latest_sales_date: object | None


def normalize_daily_sales(raw: pd.DataFrame) -> pd.DataFrame:
    _require_columns(raw, DAILY_SALES_COLUMNS.values())
    sales_date = pd.to_datetime(raw[DAILY_SALES_COLUMNS["sales_date"]], errors="coerce")
    normalized = pd.DataFrame(
        {
            "sales_year": sales_date.dt.year,
            "sales_month": sales_date.dt.month,
            "sales_date": sales_date.dt.date,
            "customer_code": raw[DAILY_SALES_COLUMNS["customer_code"]].fillna("").astype(str).str.strip(),
            "customer_name": raw[DAILY_SALES_COLUMNS["customer_name"]].fillna("").astype(str).str.strip(),
            "product_code": raw[DAILY_SALES_COLUMNS["product_code"]].map(normalize_product_code),
            "product_name": raw[DAILY_SALES_COLUMNS["product_name"]].fillna("").astype(str).str.strip(),
            "sales_quantity": _number(raw[DAILY_SALES_COLUMNS["sales_quantity"]]),
            "gift_quantity": _number(raw[DAILY_SALES_COLUMNS["gift_quantity"]]),
            "net_unit_price": _number(raw[DAILY_SALES_COLUMNS["net_unit_price"]]),
            "taxed_amount": _number(raw[DAILY_SALES_COLUMNS["taxed_amount"]]),
            "bonus_basis_amount": _number(raw[DAILY_SALES_COLUMNS["bonus_basis_amount"]]),
            "invoice_number": raw[DAILY_SALES_COLUMNS["invoice_number"]].fillna("").astype(str).str.strip(),
            "shipment_number": raw[DAILY_SALES_COLUMNS["shipment_number"]].fillna("").astype(str).str.strip(),
            "order_type": raw[DAILY_SALES_COLUMNS["order_type"]].fillna("").astype(str).str.strip(),
            "performance_type": raw[DAILY_SALES_COLUMNS["performance_type"]].fillna("").astype(str).str.strip(),
        }
    )
    normalized["actual_quantity"] = normalized["sales_quantity"] + normalized["gift_quantity"]
    normalized = normalized[
        normalized["sales_date"].notna()
        & normalized["customer_name"].astype(bool)
        & normalized["product_code"].astype(bool)
    ].copy()
    if normalized.empty:
        raise ValueError("每日業績檔沒有可匯入的明細列。")
    months = normalized[["sales_year", "sales_month"]].drop_duplicates()
    if len(months) != 1:
        raise ValueError("每日業績檔不可混用多個月份。")
    return normalized


def _number(values: pd.Series) -> pd.Series:
    return pd.to_numeric(values, errors="coerce").fillna(0)


def _require_columns(raw: pd.DataFrame, columns) -> None:
    missing = [column for column in columns if column not in raw.columns]
    if missing:
        raise ValueError(f"每日業績檔缺少欄位: {', '.join(missing)}")
```

- [ ] **Step 4: Run normalization test**

Run:

```bash
python -m pytest -q tests/test_daily_sales_importer.py::test_normalize_daily_sales_ignores_summary_rows_and_computes_quantity
```

Expected: PASS.

## Task 3: Import Workbook Transactionally

**Files:**
- Modify: `src/backend/daily_sales_importer.py`
- Modify: `tests/test_daily_sales_importer.py`

- [ ] **Step 1: Write failing import overwrite test**

Append:

```python
from io import BytesIO


def _workbook_bytes(rows: list[dict]) -> BytesIO:
    stream = BytesIO()
    pd.DataFrame(rows).to_excel(stream, index=False)
    stream.seek(0)
    return stream


def _daily_row(date: str, customer: str, product: str, qty: float, taxed_amount: float) -> dict:
    return {
        "出貨日期": date,
        "客戶代號": "C001",
        "客戶簡稱": customer,
        "產品": product,
        "產品簡稱": "Product",
        "銷售數量": qty,
        "贈品數量": 0,
        "銷貨淨價": taxed_amount / qty if qty else 0,
        "含稅淨額": taxed_amount,
        "折後業績": 0,
        "發票編號": "INV",
        "出貨單號": "SHIP",
        "單別": "正常銷",
        "業績屬性": "處方",
    }


def test_import_daily_sales_workbook_overwrites_same_month(tmp_path: Path):
    db = MORDatabase(tmp_path / "mor_workbench.db")

    first = _workbook_bytes([_daily_row("2026-05-04", "Hospital A", "P1", 5, 1000)])
    second = _workbook_bytes([_daily_row("2026-05-08", "Hospital A", "P1", 9, 1800)])

    from src.backend.daily_sales_importer import import_daily_sales_workbook

    import_daily_sales_workbook(db, first, "first.xlsx")
    result = import_daily_sales_workbook(db, second, "second.xlsx")

    with db.get_connection() as conn:
        rows = conn.execute("SELECT * FROM daily_sales_actuals").fetchall()
        batches = conn.execute("SELECT * FROM daily_import_batches ORDER BY id").fetchall()

    assert result.sales_year == 2026
    assert result.sales_month == 5
    assert result.row_count == 1
    assert len(batches) == 2
    assert len(rows) == 1
    assert rows[0]["actual_quantity"] == 9
    assert rows[0]["taxed_amount"] == 1800
```

- [ ] **Step 2: Run failing test**

Run:

```bash
python -m pytest -q tests/test_daily_sales_importer.py::test_import_daily_sales_workbook_overwrites_same_month
```

Expected: FAIL because `import_daily_sales_workbook` is not implemented.

- [ ] **Step 3: Implement import function**

Add to `src/backend/daily_sales_importer.py`:

```python
def import_daily_sales_workbook(
    db: MORDatabase,
    file_obj: BinaryIO,
    source_filename: str,
) -> DailySalesImportResult:
    payload = file_obj.read()
    source_hash = hashlib.sha256(payload).hexdigest()
    raw = pd.read_excel(BytesIO(payload))
    normalized = normalize_daily_sales(raw)
    year = int(normalized["sales_year"].iloc[0])
    month = int(normalized["sales_month"].iloc[0])
    date_start = normalized["sales_date"].min()
    date_end = normalized["sales_date"].max()
    quantity_total = float(normalized["actual_quantity"].sum())
    taxed_amount_total = float(normalized["taxed_amount"].sum())

    with db.get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO daily_import_batches
            (source_filename, source_hash, sales_year, sales_month, row_count,
             date_start, date_end, quantity_total, taxed_amount_total, status, message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'success', ?)
            """,
            (
                source_filename,
                source_hash,
                year,
                month,
                int(len(normalized)),
                str(date_start),
                str(date_end),
                quantity_total,
                taxed_amount_total,
                "匯入完成",
            ),
        )
        batch_id = int(cursor.lastrowid)
        conn.execute(
            "DELETE FROM daily_sales_actuals WHERE sales_year = ? AND sales_month = ?",
            (year, month),
        )
        rows = normalized.copy()
        rows["import_batch_id"] = batch_id
        rows[
            [
                "sales_year",
                "sales_month",
                "sales_date",
                "customer_code",
                "customer_name",
                "product_code",
                "product_name",
                "sales_quantity",
                "gift_quantity",
                "actual_quantity",
                "net_unit_price",
                "taxed_amount",
                "bonus_basis_amount",
                "invoice_number",
                "shipment_number",
                "order_type",
                "performance_type",
                "import_batch_id",
            ]
        ].to_sql("daily_sales_actuals", conn, if_exists="append", index=False)
        conn.commit()

    return DailySalesImportResult(
        batch_id=batch_id,
        sales_year=year,
        sales_month=month,
        row_count=int(len(normalized)),
        date_start=date_start,
        date_end=date_end,
        quantity_total=quantity_total,
        taxed_amount_total=taxed_amount_total,
    )
```

- [ ] **Step 4: Run import tests**

Run:

```bash
python -m pytest -q tests/test_daily_sales_importer.py
```

Expected: PASS.

## Task 4: Add Monthly Aggregate Lookup

**Files:**
- Modify: `src/backend/daily_sales_importer.py`
- Modify: `tests/test_daily_sales_importer.py`

- [ ] **Step 1: Write failing aggregate test**

Append:

```python
def test_fetch_daily_actuals_by_row_id_aggregates_quantity_and_latest_date(tmp_path: Path):
    db = MORDatabase(tmp_path / "mor_workbench.db")
    stream = _workbook_bytes(
        [
            _daily_row("2026-05-04", "Hospital A", "P1", 5, 1000),
            _daily_row("2026-05-08", "Hospital A", "P1", 2, 400),
        ]
    )

    from src.backend.daily_sales_importer import (
        fetch_daily_actuals_by_row_id,
        import_daily_sales_workbook,
    )

    import_daily_sales_workbook(db, stream, "daily.xlsx")
    actuals = fetch_daily_actuals_by_row_id(db, 2026, 5)

    row = actuals["Hospital A__P1"]
    assert row.actual_quantity == 7
    assert row.taxed_amount == 1400
    assert str(row.latest_sales_date) == "2026-05-08"
```

- [ ] **Step 2: Run failing aggregate test**

Run:

```bash
python -m pytest -q tests/test_daily_sales_importer.py::test_fetch_daily_actuals_by_row_id_aggregates_quantity_and_latest_date
```

Expected: FAIL because aggregate lookup does not exist.

- [ ] **Step 3: Implement aggregate lookup**

Add to `src/backend/daily_sales_importer.py`:

```python
def fetch_daily_actuals_by_row_id(
    db: MORDatabase,
    year: int,
    month: int,
) -> dict[str, DailyActualAggregate]:
    with db.get_connection() as conn:
        rows = conn.execute(
            """
            SELECT customer_name,
                   product_code,
                   SUM(actual_quantity) AS actual_quantity,
                   SUM(taxed_amount) AS taxed_amount,
                   MAX(sales_date) AS latest_sales_date
            FROM daily_sales_actuals
            WHERE sales_year = ? AND sales_month = ?
            GROUP BY customer_name, product_code
            """,
            (year, month),
        ).fetchall()
    return {
        f"{row['customer_name']}__{row['product_code']}": DailyActualAggregate(
            actual_quantity=float(row["actual_quantity"] or 0),
            taxed_amount=float(row["taxed_amount"] or 0),
            latest_sales_date=row["latest_sales_date"],
        )
        for row in rows
    }
```

- [ ] **Step 4: Run importer tests**

Run:

```bash
python -m pytest -q tests/test_daily_sales_importer.py
```

Expected: PASS.

## Task 5: Wire Daily Actuals Into Product Monitor Only

**Files:**
- Modify: `src/backend/operational_views.py`
- Modify: `tests/test_operational_views.py`

- [ ] **Step 1: Write failing product monitor unit test**

Add to `tests/test_operational_views.py`:

```python
from dataclasses import replace
from datetime import date

from src.backend.daily_sales_importer import DailyActualAggregate
from src.backend.forecast_models import ForecastRow
from src.backend.operational_views import build_product_monitor_rows


def test_product_monitor_current_quantity_prefers_daily_actual_lookup():
    row = ForecastRow(
        row_id="Hospital A__P1",
        customer="Hospital A",
        product_code="P1",
        product_name="Product One",
        latest_order_date=date(2026, 4, 1),
        cycle_days=None,
        next_order_date=None,
        auto_in_month=False,
        last_year_same_month_qty=10,
        this_year_same_month_qty=3,
        latest_price=100,
        system_forecast=8,
        manual_adjustment=None,
        final_forecast=8,
        estimated_amount=800,
        forecast_basis="data_driven",
    )
    actuals = {
        "Hospital A__P1": DailyActualAggregate(
            actual_quantity=12,
            taxed_amount=1200,
            latest_sales_date="2026-05-08",
        )
    }

    monitor_rows = build_product_monitor_rows([row], daily_actuals=actuals)

    assert monitor_rows[0].current_quantity == 12
```

- [ ] **Step 2: Run failing test**

Run:

```bash
python -m pytest -q tests/test_operational_views.py::test_product_monitor_current_quantity_prefers_daily_actual_lookup
```

Expected: FAIL because `build_product_monitor_rows` has no `daily_actuals` argument.

- [ ] **Step 3: Implement optional daily actual override**

In `src/backend/operational_views.py`:

- Import `DailyActualAggregate` and `fetch_daily_actuals_by_row_id`.
- Change `build_product_monitor_rows` to accept `daily_actuals: Mapping[str, DailyActualAggregate] | None = None`.
- Change `_to_monitor_row` to accept the lookup and use `actual.actual_quantity` for `current_quantity` when present.
- In `build_forecast_page_context`, load daily actuals and pass them only to `build_product_monitor_rows`.

Important: do not replace `summary.rows` in Phase 1. This keeps dashboard and forecast behavior unchanged.

- [ ] **Step 4: Run focused tests**

Run:

```bash
python -m pytest -q tests/test_operational_views.py tests/test_daily_sales_importer.py
```

Expected: PASS.

## Task 6: Add Import Route

**Files:**
- Modify: `src/backend/app.py`
- Modify: `tests/test_app.py`

- [ ] **Step 1: Write failing route test**

Add to `tests/test_app.py`:

```python
from io import BytesIO


def _daily_import_workbook() -> BytesIO:
    stream = BytesIO()
    pd.DataFrame(
        [
            {
                "出貨日期": "2026-05-04",
                "客戶代號": "C001",
                "客戶簡稱": "Hospital A",
                "產品": "P1",
                "產品簡稱": "Product One",
                "銷售數量": 5,
                "贈品數量": 1,
                "銷貨淨價": 100,
                "含稅淨額": 600,
                "折後業績": 0,
                "發票編號": "INV",
                "出貨單號": "SHIP",
                "單別": "正常銷",
                "業績屬性": "處方",
            }
        ]
    ).to_excel(stream, index=False)
    stream.seek(0)
    return stream


def test_product_monitor_import_route_stores_daily_actuals(monkeypatch):
    db_base_path = _isolated_db_base()
    config = ForecastConfig(detail_file="sales.xlsx", detail_sheet="Sales")
    columns = config.required_columns
    data = pd.DataFrame(
        [
            {
                columns[0]: 2025,
                columns[1]: 5,
                columns[2]: 10,
                columns[3]: "Hospital A",
                columns[4]: "P1",
                columns[5]: "Product One",
                columns[6]: 10,
                columns[7]: 100,
            },
            {
                columns[0]: 2026,
                columns[1]: 4,
                columns[2]: 10,
                columns[3]: "Hospital A",
                columns[4]: "P1",
                columns[5]: "Product One",
                columns[6]: 3,
                columns[7]: 100,
            },
        ]
    )
    monkeypatch.setattr(app, "load_sales_detail", lambda base_path, forecast_config: data)
    monkeypatch.setattr(operational_views, "load_sales_detail", lambda base_path, forecast_config: data)
    client = _client({"FORECAST_CONFIG": config, "DB_BASE_PATH": db_base_path})

    response = client.post(
        "/monitor/products/import",
        data={"daily_sales_file": (_daily_import_workbook(), "daily.xlsx")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "匯入完成" in html
    assert "6" in html
```

- [ ] **Step 2: Run failing route test**

Run:

```bash
python -m pytest -q tests/test_app.py::test_product_monitor_import_route_stores_daily_actuals
```

Expected: FAIL because the route does not exist.

- [ ] **Step 3: Implement route**

In `src/backend/app.py`:

- Import `import_daily_sales_workbook`.
- Add route inside `create_app`:

```python
@app.post("/monitor/products/import")
def import_product_monitor_daily_sales() -> Response:
    uploaded = request.files.get("daily_sales_file")
    if uploaded is None or not uploaded.filename:
        return redirect(url_for("product_monitor", import_error="請選擇當月累積業績檔。"))
    try:
        result = import_daily_sales_workbook(db, uploaded.stream, uploaded.filename)
        cache.clear()
    except Exception as exc:
        return redirect(url_for("product_monitor", import_error=f"匯入失敗：{exc}"))
    return redirect(
        url_for(
            "product_monitor",
            year=result.sales_year,
            month=result.sales_month,
            import_message=(
                f"匯入完成：{result.sales_year}/{result.sales_month:02d}，"
                f"{result.row_count} 筆，"
                f"數量 {result.quantity_total:,.0f}，"
                f"含稅淨額 {result.taxed_amount_total:,.0f}"
            ),
        )
    )
```

- In `product_monitor()`, pass `import_message=request.args.get("import_message")` and `import_error=request.args.get("import_error")` into the template.

- [ ] **Step 4: Run route test**

Run:

```bash
python -m pytest -q tests/test_app.py::test_product_monitor_import_route_stores_daily_actuals
```

Expected: PASS.

## Task 7: Add Upload UI

**Files:**
- Modify: `templates/product_monitor.html`
- Modify: `tests/test_app.py`

- [ ] **Step 1: Write failing template test**

Add or extend an existing product monitor test:

```python
def test_product_monitor_page_exposes_daily_sales_import_form():
    client = _client()

    html = client.get("/monitor/products").get_data(as_text=True)

    assert 'action="/monitor/products/import"' in html
    assert 'name="daily_sales_file"' in html
    assert "選擇當月累積業績檔" in html
    assert "系統將依欄位格式判斷資料，不限制檔名。" in html
```

- [ ] **Step 2: Run failing template test**

Run:

```bash
python -m pytest -q tests/test_app.py::test_product_monitor_page_exposes_daily_sales_import_form
```

Expected: FAIL because the form does not exist.

- [ ] **Step 3: Add upload form and messages**

In `templates/product_monitor.html`, above the monitor workspace section, add:

```html
<section class="workbench-panel" aria-labelledby="daily-import-title">
  <div class="workbench-toolbar">
    <div class="toolbar-title">
      <h2 id="daily-import-title">選擇當月累積業績檔</h2>
      <span>系統將依欄位格式判斷資料，不限制檔名。</span>
    </div>
    <form class="toolbar-controls" method="post" action="{{ url_for('import_product_monitor_daily_sales') }}" enctype="multipart/form-data">
      <input type="file" name="daily_sales_file" accept=".xlsx,.xls" required>
      <button type="submit">匯入</button>
    </form>
  </div>
</section>

{% if import_message %}
  <section class="alert alert-info" role="status">{{ import_message }}</section>
{% endif %}
{% if import_error %}
  <section class="alert" role="alert">{{ import_error }}</section>
{% endif %}
```

Use existing utility classes first. Only add CSS if the form looks broken in browser verification.

- [ ] **Step 4: Run app tests for product monitor**

Run:

```bash
python -m pytest -q tests/test_app.py -k "product_monitor or daily_sales_import"
```

Expected: PASS.

## Task 8: Verification and Documentation Touch-Up

**Files:**
- Modify if needed: `infrastructure/plans/2026-05-10-daily-sales-import-monthly-review-roadmap.md`
- Modify if needed: `docs/workflows/operational-interface.md`
- Modify if needed: `ROADMAP.md`

- [ ] **Step 1: Run focused backend verification**

Run:

```bash
python -m pytest -q tests/test_daily_sales_importer.py tests/test_operational_views.py tests/test_app.py -k "daily_sales or product_monitor"
```

Expected: PASS.

- [ ] **Step 2: Run full test suite**

Run:

```bash
python -m pytest -q
```

Expected: PASS.

- [ ] **Step 3: Run syntax check**

Run:

```bash
python -m py_compile app.py src/backend/app.py src/backend/database.py src/backend/daily_sales_importer.py src/backend/operational_views.py
```

Expected: no output.

- [ ] **Step 4: Optional browser verification**

If the Flask app can run locally, start it and open `/monitor/products`.

Check:

- Upload form appears above the monitor table.
- The table remains compact and operational.
- Import success and error messages do not overlap the toolbar.

- [ ] **Step 5: Commit Phase 1**

After tests pass and diff is reviewed:

```bash
git add src/backend/database.py src/backend/daily_sales_importer.py src/backend/operational_views.py src/backend/app.py templates/product_monitor.html tests/test_daily_sales_importer.py tests/test_operational_views.py tests/test_app.py
git commit -m "feat: import current-month daily sales actuals"
```

## Risk Notes

- `pandas.to_excel` in tests depends on an Excel writer already available through project dependencies. If missing, use the project’s existing Excel test pattern rather than adding a dependency.
- Product monitor row IDs depend on exact `customer_name__product_code` matching. Phase 1 should normalize product codes and preserve customer names exactly as input.
- This phase intentionally does not change dashboard metrics. If imported daily actuals should later drive dashboard actuals, handle that as a separate task after monitor behavior is stable.
- Uploaded files are parsed by columns only. Do not add filename-specific logic.
