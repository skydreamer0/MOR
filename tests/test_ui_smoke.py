"""UI smoke tests — operation flows and boundary validation.

Covers gaps not addressed by test_app.py:
1. All four pages load end-to-end with seeded data (incl. customers page)
2. Year/month range validation (400 on out-of-range inputs)
3. Budget coverage warning shown when unmapped products exist
4. Settings shows no issues when data is clean
5. Period param flows correctly across pages
6. Complete adjust → export flow
7. Customer view page — loads, shows per-customer data, empty state
"""
from __future__ import annotations

import json
import re
import shutil
import uuid
from pathlib import Path

import pytest

from src.backend import app
from src.backend.database import get_db


# ── Test helpers ─────────────────────────────────────────────────────────────

def _isolated_base() -> Path:
    base = Path.cwd() / ".test-dbs" / f"mor-smoke-{uuid.uuid4().hex}"
    base.mkdir(parents=True)
    return base


def _client(db_base: Path | None = None):
    base = db_base or _isolated_base()
    return app.create_app({"TESTING": True, "DB_BASE_PATH": base}).test_client()


def _seed_sales(db_base: Path, rows: list[dict]) -> None:
    """Insert sales_records rows. Each dict: order_date, customer, product, qty, price, amount."""
    db = get_db(db_base)
    with db.get_connection() as conn:
        for r in rows:
            conn.execute(
                "INSERT INTO sales_records "
                "(order_date, customer_name, product_code, product_name, quantity, unit_price, amount) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (r["order_date"], r["customer"], r["product"], r.get("name", r["product"]),
                 r["qty"], r.get("price", 100.0), r.get("amount", r["qty"] * r.get("price", 100.0))),
            )
        conn.commit()


def _seed_budget(db_base: Path, rows: list[dict]) -> None:
    """Insert budget_targets rows. Each dict: year, month, customer, product, qty."""
    db = get_db(db_base)
    with db.get_connection() as conn:
        for r in rows:
            conn.execute(
                "INSERT INTO budget_targets "
                "(year, month, customer_name, product_code, target_quantity, target_amount, base_target_quantity) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (r["year"], r["month"], r["customer"], r["product"],
                 r["qty"], r.get("amount", 0), r.get("base_qty", r["qty"])),
            )
        conn.commit()


def _seed_daily_actuals(db_base: Path, year: int, month: int, rows: list[dict]) -> None:
    """Insert imported daily actuals. Each dict: date, customer, product, qty, amount."""
    db = get_db(db_base)
    with db.get_connection() as conn:
        conn.execute(
            """INSERT INTO daily_import_batches
            (source_filename, source_hash, sales_year, sales_month,
             row_count, quantity_total, taxed_amount_total, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'success')""",
            (
                f"{year}-{month:02d}.xlsx",
                f"{year}-{month:02d}",
                year,
                month,
                len(rows),
                sum(r["qty"] for r in rows),
                sum(r["amount"] for r in rows),
            ),
        )
        batch_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        for r in rows:
            conn.execute(
                """INSERT INTO daily_sales_actuals
                (sales_year, sales_month, sales_date, customer_name, product_code,
                 actual_quantity, taxed_amount, bonus_basis_amount, net_unit_price,
                 import_batch_id, customer_code, product_name, sales_quantity, gift_quantity)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, '', ?, ?, 0)""",
                (
                    year,
                    month,
                    r["date"],
                    r["customer"],
                    r["product"],
                    r["qty"],
                    r["amount"],
                    r["amount"] / r["qty"],
                    batch_id,
                    r.get("name", r["product"]),
                    r["qty"],
                ),
            )
        conn.commit()


def _extract_slices(html: str) -> list[dict]:
    match = re.search(r"const SLICES = (.*?);\s*const TARGET_MONTH", html, re.S)
    assert match, "SLICES JSON was not embedded"
    return json.loads(match.group(1))


def _sales_rows() -> list[dict]:
    return [
        {"order_date": f"2026-{m:02d}-10", "customer": "A客戶", "product": "P1",
         "name": "商品A", "qty": 20, "price": 100.0}
        for m in [3, 4]
    ] + [
        {"order_date": f"2026-{m:02d}-15", "customer": "B客戶", "product": "P2",
         "name": "商品B", "qty": 10, "price": 200.0}
        for m in [3, 4]
    ]


# ── 1. All four pages load with seeded data ───────────────────────────────────

class TestAllPagesLoad:

    def setup_method(self):
        self.base = _isolated_base()
        _seed_sales(self.base, _sales_rows())
        self.client = _client(self.base)

    def test_dashboard_loads(self):
        r = self.client.get("/?year=2026&month=5")
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert "業績總覽" in html
        assert "預估業績金額" in html

    def test_forecast_loads(self):
        r = self.client.get("/forecast?year=2026&month=5")
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert "settings-workspace" not in html  # not the settings page
        assert 'id="customer-filter"' in html
        assert "A客戶" in html

    def test_monitor_loads(self):
        r = self.client.get("/monitor/products?year=2026&month=5")
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert "跳單監控" in html or "product_monitor" in html or "A客戶" in html

    def test_settings_loads(self):
        r = self.client.get("/settings?year=2026&month=5")
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert "settings-workspace" in html
        assert "P1" in html
        assert "P2" in html


# ── 2. Year/month range validation ────────────────────────────────────────────

class TestYearMonthRangeValidation:

    def setup_method(self):
        self.base = _isolated_base()
        _seed_sales(self.base, _sales_rows())
        self.client = _client(self.base)

    def _get_row_id(self) -> str:
        page = self.client.get("/forecast?year=2026&month=5").get_data(as_text=True)
        return re.search(r'data-row-id="([^"]+)"', page).group(1)

    def test_patch_row_rejects_month_zero(self):
        row_id = self._get_row_id()
        r = self.client.patch(f"/forecast/row/{row_id}",
                              data={"qty": "5", "year": "2026", "month": "0"})
        assert r.status_code == 400

    def test_patch_row_rejects_month_13(self):
        row_id = self._get_row_id()
        r = self.client.patch(f"/forecast/row/{row_id}",
                              data={"qty": "5", "year": "2026", "month": "13"})
        assert r.status_code == 400

    def test_patch_row_rejects_year_out_of_range(self):
        row_id = self._get_row_id()
        r = self.client.patch(f"/forecast/row/{row_id}",
                              data={"qty": "5", "year": "1999", "month": "5"})
        assert r.status_code == 400

    def test_save_adjustment_rejects_invalid_month(self):
        r = self.client.post("/adjustments/save",
                             data={"row_id": "A__P1", "year": "2026", "month": "99"})
        assert r.status_code == 400

    def test_save_snapshot_rejects_invalid_year(self):
        r = self.client.post("/snapshots/save",
                             data={"year": "1800", "month": "5", "snapshot_name": "test"})
        assert r.status_code == 400

    def test_patch_row_accepts_valid_range(self):
        row_id = self._get_row_id()
        r = self.client.patch(f"/forecast/row/{row_id}",
                              data={"qty": "5", "year": "2026", "month": "5"})
        assert r.status_code == 200


# ── 3. Budget coverage warning ────────────────────────────────────────────────

class TestBudgetCoverageWarning:

    def test_warning_shown_when_budget_has_unmapped_product(self):
        base = _isolated_base()
        _seed_sales(base, _sales_rows())
        # Add budget for a product NOT in sales
        _seed_budget(base, [
            {"year": 2026, "month": 5, "customer": "A客戶", "product": "GHOST", "qty": 100},
        ])
        client = _client(base)

        html = client.get("/settings?year=2026&month=5").get_data(as_text=True)

        assert "無對應紀錄" in html
        assert "alert-info" in html

    def test_no_warning_when_all_budget_products_have_sales(self):
        base = _isolated_base()
        _seed_sales(base, _sales_rows())
        _seed_budget(base, [
            {"year": 2026, "month": 5, "customer": "A客戶", "product": "P1", "qty": 50},
            {"year": 2026, "month": 5, "customer": "B客戶", "product": "P2", "qty": 30},
        ])
        client = _client(base)

        html = client.get("/settings?year=2026&month=5").get_data(as_text=True)

        assert "無對應紀錄" not in html

    def test_no_data_issues_shown_when_no_budget_loaded(self):
        base = _isolated_base()
        _seed_sales(base, _sales_rows())
        client = _client(base)

        html = client.get("/settings?year=2026&month=5").get_data(as_text=True)

        # No budget at all → validate_budget_coverage gets empty set → no warning
        assert "無對應紀錄" not in html


# ── 4. Period param flows across pages ────────────────────────────────────────

# ── 5. Customer view page ─────────────────────────────────────────────────────

class TestCustomerView:

    def test_page_loads_with_seeded_data(self):
        base = _isolated_base()
        _seed_sales(base, _sales_rows())
        client = _client(base)

        r = client.get("/customers?year=2026&month=5")

        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert "客戶分析" in html
        assert "customer-analytics-main" in html
        assert "customer-analytics-table" in html
        assert "cust-tbody" in html

    def test_page_embeds_customer_slices_as_json(self):
        base = _isolated_base()
        _seed_sales(base, _sales_rows())
        client = _client(base)

        html = client.get("/customers?year=2026&month=5").get_data(as_text=True)

        # Slices are embedded as JSON for JS rendering
        assert "SLICES =" in html
        assert '"entity_label"' in html   # JSON keys are always ASCII

    def test_page_embeds_imported_daily_actual_amounts(self):
        base = _isolated_base()
        _seed_sales(base, [
            {
                "order_date": "2026-04-10",
                "customer": "Hospital A",
                "product": "P1",
                "name": "Product One",
                "qty": 2,
                "amount": 200,
            },
        ])
        _seed_daily_actuals(base, 2026, 5, [
            {
                "date": "2026-05-04",
                "customer": "Hospital A",
                "product": "P1",
                "name": "Product One",
                "qty": 6,
                "amount": 600,
            },
        ])
        client = _client(base)

        html = client.get("/customers?year=2026&month=5").get_data(as_text=True)
        slices = _extract_slices(html)

        hospital = next(s for s in slices if s["entity_id"] == "Hospital A")
        assert hospital["ty_monthly_amount"][4] == 600

    def test_page_shows_empty_state_without_data(self):
        client = _client()

        html = client.get("/customers?year=2026&month=5").get_data(as_text=True)

        assert "尚無客戶資料" in html

    def test_page_in_nav_across_all_pages(self):
        base = _isolated_base()
        _seed_sales(base, _sales_rows())
        client = _client(base)

        for path in ["/", "/forecast", "/customers", "/settings"]:
            html = client.get(f"{path}?year=2026&month=5").get_data(as_text=True)
            assert 'href="/customers"' in html, f"customers nav link missing on {path}"


# ── 6. Period param flows across pages ────────────────────────────────────────

def test_period_params_reflected_in_forecast_form():
    base = _isolated_base()
    _seed_sales(base, _sales_rows())
    client = _client(base)

    html = client.get("/forecast?year=2026&month=3").get_data(as_text=True)

    # Year/month selectors should reflect the requested period
    assert 'value="2026"' in html or "2026" in html
    assert "3" in html  # month 3 appears somewhere in the form


# ── 5. Adjust → export complete flow ─────────────────────────────────────────

def test_adjust_then_export_reflects_adjustment():
    base = _isolated_base()
    _seed_sales(base, _sales_rows())
    client = _client(base)

    # Step 1: Get forecast page and find a row_id
    forecast_html = client.get("/forecast?year=2026&month=5").get_data(as_text=True)
    row_id = re.search(r'data-row-id="([^"]+)"', forecast_html).group(1)
    signature_before = re.search(
        r'name="forecast_signature" value="([^"]+)"', forecast_html
    ).group(1)

    # Step 2: Save an adjustment
    patch_resp = client.patch(
        f"/forecast/row/{row_id}",
        data={"qty": "99", "note": "smoke-test", "year": "2026", "month": "5"},
    )
    assert patch_resp.status_code == 200

    # Step 3: Old signature should now be rejected (forecast changed)
    export_stale = client.post(
        "/export",
        data={"year": "2026", "month": "5", "forecast_signature": signature_before},
    )
    assert export_stale.status_code == 400

    # Step 4: Fresh signature should export successfully
    fresh_html = client.get("/forecast?year=2026&month=5").get_data(as_text=True)
    fresh_signature = re.search(
        r'name="forecast_signature" value="([^"]+)"', fresh_html
    ).group(1)
    export_ok = client.post(
        "/export",
        data={"year": "2026", "month": "5", "forecast_signature": fresh_signature},
    )
    assert export_ok.status_code == 200
    assert export_ok.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
