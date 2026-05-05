from pathlib import Path
import re
import shutil
import sqlite3
import uuid

import pandas as pd

from src.backend import app, operational_views
from src.backend.forecast_config import ForecastConfig


def _isolated_db_base() -> Path:
    base = Path.cwd() / ".test-dbs" / f"mor-test-{uuid.uuid4().hex}"
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True)
    return base


def _client(config: dict | None = None):
    app_config = {"TESTING": True, "DB_BASE_PATH": _isolated_db_base()}
    app_config.update(config or {})
    return app.create_app(app_config).test_client()


def test_homepage_loads_dashboard():
    client = _client()

    response = client.get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "<title>MOR" in html
    assert "<h1>MOR " in html
    assert "業績總覽" in html
    assert "預算目標" in html
    assert "預估達成" in html
    assert "預估業績金額" in html
    assert "金額 GAP" in html
    assert "高風險追蹤" in html
    assert "metrics.target_quantity" not in html
    assert 'href="/forecast"' in html


def test_dashboard_reuses_forecast_context_when_excel_mtime_is_unchanged(monkeypatch):
    calls = {"count": 0}
    real_builder = app.build_forecast_page_context

    def counting_builder(*args, **kwargs):
        calls["count"] += 1
        return real_builder(*args, **kwargs)

    monkeypatch.setattr(app, "build_forecast_page_context", counting_builder)
    client = _client()

    first = client.get("/")
    second = client.get("/")

    assert first.status_code == 200
    assert second.status_code == 200
    assert calls["count"] == 1


def test_forecast_reuses_dashboard_context_cache(monkeypatch):
    calls = {"count": 0}
    real_builder = app.build_forecast_page_context

    def counting_builder(*args, **kwargs):
        calls["count"] += 1
        return real_builder(*args, **kwargs)

    monkeypatch.setattr(app, "build_forecast_page_context", counting_builder)
    client = _client()

    dashboard_response = client.get("/")
    forecast_response = client.get("/forecast")

    assert dashboard_response.status_code == 200
    assert forecast_response.status_code == 200
    assert calls["count"] == 1


def test_homepage_data_health_alert_appears_before_progress_hero():
    client = _client()

    response = client.get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'class="alert alert-info' in html
    assert html.index('class="alert alert-info') < html.index('class="hero__container"')


def test_forecast_page_renders_forecast_review_assets_and_tools():
    client = _client()

    response = client.get("/forecast")
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


def test_frontend_pages_load_htmx_assets():
    client = _client()

    dashboard = client.get("/").get_data(as_text=True)
    forecast = client.get("/forecast").get_data(as_text=True)

    assert "https://unpkg.com/htmx.org@1.9.10" in dashboard
    assert "https://unpkg.com/htmx.org@1.9.10" in forecast


def test_dashboard_metrics_partial_renders_fragment_only():
    client = _client()

    response = client.get("/dashboard/metrics")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "<html" not in html
    assert 'class="hero__container"' in html
    assert "業績總覽" in html


def test_dashboard_copy_does_not_render_mojibake():
    client = _client()

    html = client.get("/").get_data(as_text=True)
    metrics = client.get("/dashboard/metrics").get_data(as_text=True)
    rendered = html + metrics

    assert "業績總覽" in rendered
    assert "預估調整" in rendered
    assert "產品跳單監控" in rendered
    assert "系統設定" in rendered
    assert "年度" in rendered
    assert "月份" in rendered
    assert "套用" in rendered
    assert "預估達成" in rendered
    assert "實績金額" in rendered
    assert "高風險產品" in rendered
    assert "跳單狀態" in rendered
    for broken in ("璆剔蜀蝮質汗", "摰Ｘ", "憸券", "擃", "??/", "?", "?"):
        assert broken not in rendered


def test_rendered_pages_do_not_show_mojibake():
    client = _client()

    forecast = client.get("/forecast").get_data(as_text=True)
    product_monitor = client.get("/monitor/products").get_data(as_text=True)
    settings = client.get("/settings").get_data(as_text=True)
    page = client.get("/forecast").get_data(as_text=True)
    row_id = re.search(r'data-row-id="([^"]+)"', page).group(1)
    row_fragment = client.patch(
        f"/forecast/row/{row_id}",
        data={"qty": "", "note": "", "year": "2026", "month": "5"},
    ).get_data(as_text=True)
    rendered = forecast + product_monitor + settings + row_fragment

    assert "自動預估" in rendered
    assert "未到期" in rendered
    assert "還原系統預估" in rendered
    assert "原因..." in rendered
    assert "排除" in rendered
    assert "缺預算" in rendered
    assert "納入" in rendered
    for broken in ("??/", "?祆", "?芸", "?", "?", "頝喳", "蝯梢", ""):
        assert broken not in rendered


def test_dashboard_period_inputs_target_metrics_zone():
    client = _client()

    response = client.get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'id="metrics-zone"' in html
    assert 'hx-get="/dashboard/metrics"' in html
    assert 'hx-target="#metrics-zone"' in html


def test_patch_forecast_row_updates_adjustment_and_returns_row_fragment():
    client = _client()
    page = client.get("/forecast").get_data(as_text=True)
    row_id = re.search(r'data-row-id="([^"]+)"', page).group(1)

    response = client.patch(
        f"/forecast/row/{row_id}",
        data={"qty": "7.5", "note": "reviewed", "year": "2026", "month": "5"},
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert html.lstrip().startswith("<tr")
    assert f'id="row-{row_id}"' in html
    assert 'value="7.5"' in html
    assert 'value="reviewed"' in html


def test_forecast_page_exposes_customer_filter_and_row_metadata():
    client = _client()

    response = client.get("/forecast")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'id="customer-filter"' in html
    assert "filterRows(this.value)" in html
    assert 'data-customer="' in html
    assert 'data-risk="' in html


def test_forecast_page_exposes_expand_all_for_collapsed_low_risk_rows():
    client = _client()

    response = client.get("/forecast")
    html = response.get_data(as_text=True)
    css = Path("static/css/mor.css").read_text(encoding="utf-8")

    assert response.status_code == 200
    assert 'id="expand-all-btn"' in html
    assert "function expandAll()" in html
    assert "forecast-table__row--collapsed" in html
    assert ".forecast-table__row--collapsed" in css


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
    monkeypatch.setattr(operational_views, "load_sales_detail", lambda base_path, forecast_config: data)
    client = _client({"FORECAST_CONFIG": config, "DB_BASE_PATH": db_base_path})

    expectations = {
        "/": 'href="/" aria-current="page"',
        "/forecast": 'href="/forecast" aria-current="page"',
        "/monitor/products": 'href="/monitor/products" aria-current="page"',
        "/settings": 'href="/settings" aria-current="page"',
    }
    for path, active_link in expectations.items():
        response = client.get(path)
        html = response.get_data(as_text=True)

        assert response.status_code == 200
        assert 'href="/"' in html
        assert 'href="/forecast"' in html
        assert 'href="/monitor/products"' in html
        assert 'href="/settings"' in html
        assert 'href="/exclusions"' not in html
        assert active_link in html
        assert "同步資料" in html


def test_old_exclusions_page_redirects_to_item_management(monkeypatch):
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
    monkeypatch.setattr(operational_views, "load_sales_detail", lambda base_path, forecast_config: data)
    client = _client({"FORECAST_CONFIG": config, "DB_BASE_PATH": db_base_path})

    response = client.get("/exclusions")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/settings")


def test_item_management_exclusion_is_reflected_on_workbench(monkeypatch):
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
    monkeypatch.setattr(operational_views, "load_sales_detail", lambda base_path, forecast_config: data)
    client = _client({"FORECAST_CONFIG": config, "DB_BASE_PATH": db_base_path})

    response = client.post(
        "/items/save",
        data={
            "product_codes": ["P1", "P2"],
            "is_budgeted_P1": "1",
            "is_visible_P1": "1",
            "is_budgeted_P2": "1",
            "is_visible_P2": "1",
            "is_excluded_P2": "1",
        },
    )
    workbench = client.get("/forecast").get_data(as_text=True)

    assert response.status_code == 200
    assert re.search(r'data-search="[^"]*Product Two"[^>]*data-excluded="true"', workbench)


def test_item_settings_save_price_quantity_and_forecast_uses_it(monkeypatch):
    db_base_path = _isolated_db_base()
    config = ForecastConfig(detail_file="sales.xlsx", detail_sheet="Sales")
    columns = config.required_columns
    data = pd.DataFrame(
        [
            {
                columns[0]: 2026,
                columns[1]: month,
                columns[2]: 10,
                columns[3]: "Hospital A",
                columns[4]: "P1",
                columns[5]: "Product One",
                columns[6]: 300,
                columns[7]: 3200,
            }
            for month in (1, 2, 3)
        ]
    )
    monkeypatch.setattr(app, "load_sales_detail", lambda base_path, forecast_config: data)
    monkeypatch.setattr(operational_views, "load_sales_detail", lambda base_path, forecast_config: data)
    client = _client({"FORECAST_CONFIG": config, "DB_BASE_PATH": db_base_path})
    with sqlite3.connect(db_base_path / "mor_workbench.db") as conn:
        conn.execute(
            """
            INSERT INTO budget_targets
            (year, month, customer_name, product_code, target_quantity, target_amount, base_target_quantity)
            VALUES (2026, 4, 'Hospital A', 'P1', 300, 3000, 1)
            """
        )
        conn.commit()

    settings = client.get("/settings?year=2026&month=4").get_data(as_text=True)
    assert 'name="price_quantity_P1"' in settings

    response = client.post(
        "/items/save",
        data={
            "product_codes": ["P1"],
            "is_budgeted_P1": "1",
            "is_visible_P1": "1",
            "price_quantity_P1": "100",
        },
    )
    forecast = client.get("/forecast?year=2026&month=4").get_data(as_text=True)

    assert response.status_code == 200
    with sqlite3.connect(db_base_path / "mor_workbench.db") as conn:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(item_configs)")]
        saved = conn.execute("SELECT price_quantity FROM item_configs WHERE product_code = 'P1'").fetchone()
    assert "price_quantity" in columns
    assert saved == (100,)
    assert 'data-price-quantity="100' in forecast
    assert ">9,600</td>" in forecast


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

    client = _client({"DB_BASE_PATH": db_base_path})

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


def test_forecast_page_renders_review_validation_and_accessibility_hooks():
    client = _client()

    response = client.get("/forecast")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'aria-label="人工調整數量"' in html
    assert 'data-validation-message' in html
    assert "人工數量必須是 0 以上的數字" in html


def test_forecast_rows_expose_dashboard_jump_anchor():
    client = _client()

    response = client.get("/forecast")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    row_id = re.search(r'data-row-id="([^"]+)"', html).group(1)
    assert f'id="row-{row_id}"' in html


def test_static_assets_define_invalid_row_validation_behavior():
    css = Path("static/css/mor.css").read_text(encoding="utf-8")
    js = Path("static/js/forecast-table.js").read_text(encoding="utf-8")

    assert "tr.invalid" in css
    assert "validateBeforeSubmit" in js
    assert "aria-invalid" in js
    assert "data-unrendered-total" in js


def test_forecast_table_compares_live_gap_to_budget():
    js = Path("static/js/forecast-table.js").read_text(encoding="utf-8")

    assert "const gap = finalQty - budget;" in js
    assert "finalQty - state.actualQuantity" not in js


def test_forecast_table_totals_only_include_budgeted_rows():
    js = Path("static/js/forecast-table.js").read_text(encoding="utf-8")
    row_template = Path("templates/_forecast_row.html").read_text(encoding="utf-8")

    assert "budgetQuantity: Number(row.dataset.budget || 0)" in js
    assert "priceQuantity: Number(row.dataset.priceQuantity || 1)" in js
    assert "(finalForecastQuantity(state) / priceQuantity) * state.price" in js
    assert "state.budgetQuantity <= 0" in js
    assert "data-price-quantity=" in row_template


def test_css_keeps_letter_spacing_neutral_for_dense_operational_ui():
    css = Path("static/css/mor.css").read_text(encoding="utf-8")

    non_zero_letter_spacing = [
        value.strip()
        for value in re.findall(r"letter-spacing:\s*([^;]+);", css)
        if value.strip() not in {"0", "0em", "0px"}
    ]

    assert non_zero_letter_spacing == []


def test_dashboard_css_uses_bem_class_names():
    css = Path("static/css/mor.css").read_text(encoding="utf-8")
    dashboard = Path("templates/_dashboard_metrics.html").read_text(encoding="utf-8")
    for old_selector in (".progress-hero", ".sub-metrics", ".risk-summary", ".customer-rank", ".row-collapsed"):
        assert old_selector not in css
    for old_class in (
        'class="progress-hero',
        'class="sub-metrics',
        'class="risk-summary',
        'class="customer-rank',
        'class="row-collapsed',
    ):
        assert old_class not in dashboard

    assert "hero__container" in css + dashboard
    assert "hero__sub-metrics" in css + dashboard
    assert "risk-panel__summary" in css + dashboard
    assert "risk-panel__customer-rank" in css + dashboard
    assert "forecast-table__row--collapsed" in css


def test_homepage_shows_friendly_error_for_missing_data_file():
    missing_base = Path.cwd() / "__missing_sales_data__"
    client = _client({"DATA_BASE_PATH": missing_base})

    response = client.get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'role="alert"' in html
    assert "無法產生預估" in html


def test_homepage_exposes_unrendered_total_when_rows_are_limited(monkeypatch):
    config = ForecastConfig(detail_file="sales.xlsx", detail_sheet="Sales", visible_row_limit=1)
    db_base_path = _isolated_db_base()
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
    monkeypatch.setattr(operational_views, "load_sales_detail", lambda base_path, forecast_config: pd.DataFrame(rows))
    client = _client({"FORECAST_CONFIG": config, "DB_BASE_PATH": db_base_path})
    with sqlite3.connect(db_base_path / "mor_workbench.db") as conn:
        conn.execute(
            """
            INSERT INTO budget_targets
            (year, month, customer_name, product_code, target_quantity, target_amount, base_target_quantity)
            VALUES (2026, 4, 'B', 'P2', 10, 1000, 10)
            """
        )
        conn.commit()

    response = client.get("/forecast")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert html.count("data-row-id=") == 1
    assert 'data-unrendered-total value="1000.0"' in html
    assert "1 / 2" in html


def test_product_monitor_page_renders_drop_table(monkeypatch):
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
                columns[6]: 100,
                columns[7]: 100,
            },
            {
                columns[0]: 2026,
                columns[1]: 4,
                columns[2]: 10,
                columns[3]: "Hospital A",
                columns[4]: "P1",
                columns[5]: "Product One",
                columns[6]: 40,
                columns[7]: 100,
            },
        ]
    )
    monkeypatch.setattr(app, "load_sales_detail", lambda base_path, forecast_config: data)
    monkeypatch.setattr(operational_views, "load_sales_detail", lambda base_path, forecast_config: data)
    client = _client({"FORECAST_CONFIG": config})

    response = client.get("/monitor/products?year=2026&month=5")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "產品跳單監控" in html
    assert "去年同期數量" in html
    assert "跳單狀態" in html
    assert "高風險" in html
    assert "data-monitor-search" in html


def test_settings_page_renders_item_config_and_data_checks(monkeypatch):
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
                columns[7]: 0,
            }
        ]
    )
    monkeypatch.setattr(app, "load_sales_detail", lambda base_path, forecast_config: data)
    monkeypatch.setattr(operational_views, "load_sales_detail", lambda base_path, forecast_config: data)
    client = _client({"FORECAST_CONFIG": config, "DB_BASE_PATH": db_base_path})

    response = client.get("/settings")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "系統設定 / 資料檢核" in html
    assert "排除預估" in html
    assert "預算資料檢查" in html
    assert "訂單資料檢查" in html
    assert "品項合併設定" in html
    assert "待建" in html


def test_dashboard_and_settings_share_data_issue_messages(monkeypatch):
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
                columns[7]: 0,
            }
        ]
    )
    monkeypatch.setattr(app, "load_sales_detail", lambda base_path, forecast_config: data)
    monkeypatch.setattr(operational_views, "load_sales_detail", lambda base_path, forecast_config: data)
    client = _client({"FORECAST_CONFIG": config, "DB_BASE_PATH": db_base_path})

    dashboard = client.get("/").get_data(as_text=True)
    settings = client.get("/settings").get_data(as_text=True)

    assert "有 1 筆缺少預算目標" in dashboard
    assert "有 1 筆缺少預算目標" in settings
    assert "有 1 筆單價為 0" in dashboard
    assert "有 1 筆單價為 0" in settings


def test_items_route_redirects_to_settings():
    client = _client()

    response = client.get("/items")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/settings")


def test_settings_page_exposes_item_search_tools(monkeypatch):
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
    monkeypatch.setattr(operational_views, "load_sales_detail", lambda base_path, forecast_config: data)
    client = _client({"FORECAST_CONFIG": config, "DB_BASE_PATH": db_base_path})

    response = client.get("/settings")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'src="/static/js/item-settings.js"' in html
    assert "data-item-search" in html
    assert "data-item-visible" in html
    assert re.search(r'data-item-row[^>]+data-search="[^"]*Product One[^"]*P1', html)


def test_export_rejects_unknown_review_row_id_without_workbook():
    client = _client()

    response = client.post(
        "/export",
        data={"year": "2026", "month": "5", "manual_quantity__missing__row": "10"},
    )

    assert response.status_code == 400
    assert "Unknown forecast row" in response.get_data(as_text=True)


def test_export_accepts_current_forecast_signature():
    client = _client()
    review_response = client.get("/forecast?year=2026&month=5")
    signature = re.search(
        r'name="forecast_signature" value="([^"]+)"',
        review_response.get_data(as_text=True),
    ).group(1)

    export_response = client.post(
        "/export",
        data={"year": "2026", "month": "5", "forecast_signature": signature},
    )

    assert export_response.status_code == 200
    assert export_response.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


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
    monkeypatch.setattr(operational_views, "load_sales_detail", lambda base_path, forecast_config: loaded_data[-1])
    client = _client({"FORECAST_CONFIG": config})

    review_response = client.get("/forecast")
    signature = re.search(r'name="forecast_signature" value="([^"]+)"', review_response.get_data(as_text=True)).group(1)
    loaded_data.append(make_rows(99))

    export_response = client.post(
        "/export",
        data={"year": "2026", "month": "4", "forecast_signature": signature},
    )

    assert export_response.status_code == 400
    assert "Forecast review changed" in export_response.get_data(as_text=True)


def test_export_rejects_invalid_manual_quantity_without_500():
    client = _client()

    response = client.post(
        "/export",
        data={"year": "2026", "month": "5", "manual_quantity__A__P1": "abc"},
    )

    assert response.status_code == 400
    assert "人工數量" in response.get_data(as_text=True)
