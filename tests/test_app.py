from pathlib import Path
import re
import shutil
import sqlite3
import uuid

import pandas as pd

from src.backend import app
from src.backend.forecast_config import ForecastConfig


def _isolated_db_base() -> Path:
    base = Path.cwd() / ".test-dbs" / f"mor-test-{uuid.uuid4().hex}"
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True)
    return base


def test_homepage_loads_with_forecast_table():
    client = app.create_app({"TESTING": True}).test_client()

    response = client.get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "<title>MOR</title>" in html
    assert "<h1>MOR " in html
    assert "匯出 Excel" in html
    assert "預估總金額" in html


def test_homepage_renders_forecast_review_assets_and_tools():
    client = app.create_app({"TESTING": True}).test_client()

    response = client.get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'href="/static/css/mor.css"' in html
    assert 'src="/static/js/forecast-table.js"' in html
    assert 'class="forecast-tools"' in html
    assert "搜尋客戶或品項" in html
    assert "狀態篩選" in html
    assert "data-filter-search" in html
    assert "data-filter-status" in html
    assert "data-edited-count" in html
    assert "data-row-id=" in html
    assert "data-status=" in html
    assert "data-search=" in html


def test_header_navigation_is_consistent_across_frontend_pages(monkeypatch):
    db_base_path = _isolated_db_base()
    config = ForecastConfig(detail_file="sales.xlsx", detail_sheet="Sales")
    columns = config.required_columns
    data = pd.DataFrame(
        [
            {
                columns[0]: 2026,
                columns[1]: 4,
                columns[2]: 10,
                columns[3]: "Hospital A",
                columns[4]: "P1",
                columns[5]: "Product One",
                columns[6]: 3,
                columns[7]: 100,
            }
        ]
    )
    monkeypatch.setattr(app, "load_sales_detail", lambda base_path, forecast_config: data)
    client = app.create_app(
        {"TESTING": True, "FORECAST_CONFIG": config, "DB_BASE_PATH": db_base_path}
    ).test_client()

    expectations = {
        "/": 'href="/" aria-current="page"',
        "/items": 'href="/items" aria-current="page"',
        "/exclusions": 'href="/exclusions" aria-current="page"',
    }
    for path, active_link in expectations.items():
        response = client.get(path)
        html = response.get_data(as_text=True)

        assert response.status_code == 200
        assert 'href="/">工作台</a>' in html or active_link == 'href="/" aria-current="page"'
        assert 'href="/items"' in html
        assert 'href="/exclusions"' in html
        assert active_link in html
        assert "同步資料" in html


def test_exclusions_page_loads_and_saves_item_exclusions(monkeypatch):
    db_base_path = _isolated_db_base()
    config = ForecastConfig(detail_file="sales.xlsx", detail_sheet="Sales")
    columns = config.required_columns
    data = pd.DataFrame(
        [
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
            {
                columns[0]: 2026,
                columns[1]: 4,
                columns[2]: 10,
                columns[3]: "Hospital A",
                columns[4]: "P2",
                columns[5]: "Product Two",
                columns[6]: 5,
                columns[7]: 200,
            },
        ]
    )
    monkeypatch.setattr(app, "load_sales_detail", lambda base_path, forecast_config: data)
    client = app.create_app(
        {"TESTING": True, "FORECAST_CONFIG": config, "DB_BASE_PATH": db_base_path}
    ).test_client()

    response = client.get("/exclusions")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "排除品項管理" in html
    assert "Product One" in html

    save_response = client.post("/exclusions/save", data={"excluded_item_ids": ["P2"]})
    saved_html = save_response.get_data(as_text=True)

    assert save_response.status_code == 200
    assert 'value="P2"' in saved_html
    assert 'value="P2" \n                       checked' in saved_html


def test_adjustment_save_migrates_old_database_without_updated_by():
    db_base_path = _isolated_db_base()
    db_path = db_base_path / "mor_workbench.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE forecast_adjustments (
                year INTEGER,
                month INTEGER,
                customer_name TEXT,
                product_code TEXT,
                manual_quantity REAL,
                adjustment_reason TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (year, month, customer_name, product_code)
            )
            """
        )
        conn.commit()

    client = app.create_app({"TESTING": True, "DB_BASE_PATH": db_base_path}).test_client()

    response = client.post(
        "/adjustments/save",
        data={
            "row_id": "Hospital A__P1",
            "manual_adjustment": "12",
            "reason": "Review",
            "year": "2026",
            "month": "5",
        },
    )

    assert response.status_code == 200
    with sqlite3.connect(db_path) as conn:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(forecast_adjustments)")]
        saved = conn.execute(
            """
            SELECT manual_quantity, adjustment_reason, updated_by
            FROM forecast_adjustments
            WHERE year = 2026 AND month = 5 AND customer_name = 'Hospital A' AND product_code = 'P1'
            """
        ).fetchone()
    assert "updated_by" in columns
    assert saved == (12, "Review", "User")


def test_homepage_renders_review_validation_and_accessibility_hooks():
    client = app.create_app({"TESTING": True}).test_client()

    response = client.get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'aria-label="人工調整數量"' in html
    assert 'data-validation-message' in html
    assert "人工數量必須是 0 以上的數字" in html


def test_static_assets_define_invalid_row_validation_behavior():
    css = Path("static/css/mor.css").read_text(encoding="utf-8")
    js = Path("static/js/forecast-table.js").read_text(encoding="utf-8")

    assert "tr.invalid" in css
    assert "validateBeforeSubmit" in js
    assert "aria-invalid" in js
    assert "data-unrendered-total" in js


def test_homepage_shows_friendly_error_for_missing_data_file():
    missing_base = Path.cwd() / "__missing_sales_data__"
    client = app.create_app({"TESTING": True, "DATA_BASE_PATH": missing_base}).test_client()

    response = client.get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'role="alert"' in html
    assert "無法產生預估" in html


def test_homepage_exposes_unrendered_total_when_rows_are_limited(monkeypatch):
    config = ForecastConfig(detail_file="sales.xlsx", detail_sheet="Sales", visible_row_limit=1)
    columns = config.required_columns
    rows = []
    for customer, product_code in (("A", "P1"), ("B", "P2")):
        for month in (1, 2, 3):
            rows.append(
                {
                    columns[0]: 2026,
                    columns[1]: month,
                    columns[2]: 15,
                    columns[3]: customer,
                    columns[4]: product_code,
                    columns[5]: f"Product {product_code}",
                    columns[6]: 10,
                    columns[7]: 100,
                }
            )
    monkeypatch.setattr(app, "load_sales_detail", lambda base_path, forecast_config: pd.DataFrame(rows))
    client = app.create_app({"TESTING": True, "FORECAST_CONFIG": config}).test_client()

    response = client.get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert html.count("data-row-id=") == 1
    assert 'data-unrendered-total value="1000.0"' in html
    assert "1 / 2" in html


def test_export_rejects_unknown_review_row_id_without_workbook():
    client = app.create_app({"TESTING": True}).test_client()

    response = client.post(
        "/export",
        data={"year": "2026", "month": "5", "manual_quantity__missing__row": "10"},
    )

    assert response.status_code == 400
    assert "Unknown forecast row" in response.get_data(as_text=True)


def test_export_rejects_stale_forecast_signature(monkeypatch):
    config = ForecastConfig(detail_file="sales.xlsx", detail_sheet="Sales", visible_row_limit=1)
    columns = config.required_columns

    def make_rows(second_customer_quantity):
        rows = []
        for customer, product_code, quantity in (("A", "P1", 10), ("B", "P2", second_customer_quantity)):
            for month in (1, 2, 3):
                rows.append(
                    {
                        columns[0]: 2026,
                        columns[1]: month,
                        columns[2]: 15,
                        columns[3]: customer,
                        columns[4]: product_code,
                        columns[5]: f"Product {product_code}",
                        columns[6]: quantity,
                        columns[7]: 100,
                    }
                )
        return pd.DataFrame(rows)

    loaded_data = [make_rows(10)]
    monkeypatch.setattr(app, "load_sales_detail", lambda base_path, forecast_config: loaded_data[-1])
    client = app.create_app({"TESTING": True, "FORECAST_CONFIG": config}).test_client()

    review_response = client.get("/")
    signature = re.search(r'name="forecast_signature" value="([^"]+)"', review_response.get_data(as_text=True)).group(1)
    loaded_data.append(make_rows(99))

    export_response = client.post(
        "/export",
        data={"year": "2026", "month": "4", "forecast_signature": signature},
    )

    assert export_response.status_code == 400
    assert "Forecast review changed" in export_response.get_data(as_text=True)


def test_export_rejects_invalid_manual_quantity_without_500():
    client = app.create_app({"TESTING": True}).test_client()

    response = client.post(
        "/export",
        data={"year": "2026", "month": "5", "manual_quantity__A__P1": "abc"},
    )

    assert response.status_code == 400
    assert "人工數量" in response.get_data(as_text=True)
