from io import BytesIO
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
    assert "<h1>MOR</h1>" in html
    assert '<h1>MOR <span class="app-subtitle">' not in html
    assert "業績總覽" in html
    assert '<a href="/" aria-current="page">業績總覽</a>' in html
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


def test_homepage_data_health_alert_appears_before_progress_hero(monkeypatch):
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
                columns[8]: 0,
            }
        ]
    )
    monkeypatch.setattr(app, "load_sales_detail", lambda base_path, forecast_config: data)
    monkeypatch.setattr(operational_views, "load_sales_detail", lambda base_path, forecast_config: data)
    client = _client({"FORECAST_CONFIG": config, "DB_BASE_PATH": db_base_path})

    response = client.get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'class="alert alert-info' in html
    assert html.index('class="alert alert-info') < html.index('class="hero__container workbench-panel"')


def test_forecast_page_renders_forecast_review_assets_and_tools():
    client = _client()

    response = client.get("/forecast")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'href="/static/css/mor.css"' in html
    assert 'src="/static/js/forecast-table.js"' in html
    assert 'class="forecast-tools workbench-toolbar"' in html
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


def test_frontend_pages_do_not_load_google_inter_font():
    client = _client()

    pages = [
        client.get("/").get_data(as_text=True),
        client.get("/forecast").get_data(as_text=True),
        client.get("/monitor/products").get_data(as_text=True),
        client.get("/settings").get_data(as_text=True),
    ]
    rendered = "\n".join(pages)

    assert "fonts.googleapis.com" not in rendered
    assert "fonts.gstatic.com" not in rendered
    assert "Inter:wght" not in rendered


def test_dashboard_metrics_partial_renders_fragment_only():
    client = _client()

    response = client.get("/dashboard/metrics")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "<html" not in html
    assert 'class="hero__container workbench-panel"' in html
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
    assert "本月預算為 0" in rendered
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
    assert 'value="7"' in html
    assert 'value="reviewed"' in html


def test_forecast_page_exposes_customer_filter_and_row_metadata():
    client = _client()

    response = client.get("/forecast")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'id="customer-filter"' in html
    # customer filter now uses data-filter-customer (picked up by bindForecastTable in forecast-table.js)
    # instead of the old onchange="filterRows(this.value)" inline handler
    assert 'data-filter-customer' in html
    assert 'data-customer="' in html
    assert 'data-risk="' in html


def test_forecast_page_exposes_view_toggle_for_risk_rows():
    client = _client()

    response = client.get("/forecast")
    html = response.get_data(as_text=True)
    css = Path("static/css/mor.css").read_text(encoding="utf-8")

    assert response.status_code == 200
    assert 'id="btn-anomaly-only"' in html
    assert 'id="btn-show-all"' in html
    # collapsed class is applied client-side by applyViewMode()
    js = Path("static/js/forecast-table.js").read_text(encoding="utf-8")
    assert "forecast-table__row--collapsed" in js
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
                columns[8]: 0,
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


def test_workbench_toolbars_use_shared_structure_classes():
    client = _client()

    pages = {
        "/forecast": client.get("/forecast").get_data(as_text=True),
        "/monitor/products": client.get("/monitor/products").get_data(as_text=True),
        "/settings": client.get("/settings").get_data(as_text=True),
    }
    css = Path("static/css/mor.css").read_text(encoding="utf-8")

    for html in pages.values():
        assert "workbench-toolbar" in html
        assert "toolbar-title" in html
        assert "toolbar-controls" in html

    assert "toolbar-actions" in pages["/forecast"]
    assert "toolbar-actions" in pages["/settings"]
    assert "data-filter-search" in pages["/forecast"]
    assert "data-monitor-search" in pages["/monitor/products"]
    assert "data-item-search" in pages["/settings"]
    assert ".workbench-toolbar" in css
    assert ".toolbar-title" in css
    assert ".toolbar-controls" in css
    assert ".toolbar-actions" in css


def test_workbench_panels_and_tables_use_shared_container_classes():
    client = _client()

    dashboard = client.get("/").get_data(as_text=True)
    forecast = client.get("/forecast").get_data(as_text=True)
    monitor = client.get("/monitor/products").get_data(as_text=True)
    settings = client.get("/settings").get_data(as_text=True)
    css = Path("static/css/mor.css").read_text(encoding="utf-8")

    assert 'class="hero__container workbench-panel' in dashboard
    assert "risk-panel__summary panel workbench-panel" in dashboard
    assert "risk-panel__customer-rank panel workbench-panel" in dashboard
    assert 'class="panel workbench-panel"' in dashboard
    assert "table-wrap compact-table workbench-table-shell" in dashboard

    assert "table-wrap forecast-table-shell workbench-table-shell" in forecast
    assert "monitor-workspace workbench-panel" in monitor
    assert "table-wrap monitor-table-wrap workbench-table-shell" in monitor
    assert "settings-workspace workbench-panel" in settings
    assert "table-wrap settings-table-wrap workbench-table-shell" in settings

    assert ".workbench-panel" in css
    assert ".workbench-table-shell" in css


def test_templates_use_shared_head_assets_and_no_static_inline_layout():
    page_templates = [
        Path("templates/index.html"),
        Path("templates/forecast.html"),
        Path("templates/product_monitor.html"),
        Path("templates/settings.html"),
        Path("templates/items.html"),
    ]
    for template_path in page_templates:
        html = template_path.read_text(encoding="utf-8")
        assert '{% include "_head_assets.html" %}' in html
        assert "https://unpkg.com/htmx.org" not in html
        assert "css/mor.css" not in html

    dashboard_partial = Path("templates/_dashboard_metrics.html").read_text(encoding="utf-8")
    head_assets = Path("templates/_head_assets.html").read_text(encoding="utf-8")
    items_template = Path("templates/items.html").read_text(encoding="utf-8")
    css = Path("static/css/mor.css").read_text(encoding="utf-8")

    assert "https://unpkg.com/htmx.org@1.9.10/dist/htmx.min.js" in head_assets
    assert "D1Kt99CQMDuVetoL1lrYwg5t+9QdHe7NLX/SoJYkXDFfX37iInKRy5xLSi8nO7UC" in head_assets
    assert 'style="color:var(--accent-2)"' not in dashboard_partial
    assert 'style="margin:var(--sp-4) 0 0;"' not in dashboard_partial
    assert 'style="display:flex;gap:8px;align-items:center;"' not in dashboard_partial
    assert 'style="color: var(--muted);"' not in items_template

    assert "dist-count--caution" in dashboard_partial
    assert "empty-note" in dashboard_partial
    assert "section-actions" in dashboard_partial
    assert "item-code" in items_template
    assert ".dist-count--caution" in css
    assert ".empty-note" in css
    assert ".section-actions" in css
    assert ".item-code" in css


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
                columns[8]: 0,
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
                columns[8]: 0,
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
                columns[8]: 0,
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
                columns[8]: 0,
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


def test_forecast_page_layers_discontinued_items_below_active_rows(monkeypatch):
    db_base_path = _isolated_db_base()
    config = ForecastConfig(detail_file="sales.xlsx", detail_sheet="Sales")
    columns = config.required_columns
    data = pd.DataFrame(
        [
            {
                columns[0]: year,
                columns[1]: month,
                columns[2]: 10,
                columns[3]: customer,
                columns[4]: product_code,
                columns[5]: product_name,
                columns[6]: quantity,
                columns[7]: price,
                columns[8]: 0,
            }
            for year, month, customer, product_code, product_name, quantity, price in (
                (2026, 2, "Hospital A", "P1", "Product Active", 10, 100),
                (2026, 3, "Hospital A", "P1", "Product Active", 10, 100),
                (2026, 4, "Hospital A", "P1", "Product Active", 10, 100),
                (2025, 5, "Hospital A", "P2", "Product Old", 100, 100),
            )
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
            "item_status_P1": "active",
            "is_budgeted_P2": "1",
            "is_visible_P2": "1",
            "item_status_P2": "discontinued",
        },
    )
    forecast = client.get("/forecast?year=2026&month=5").get_data(as_text=True)

    assert response.status_code == 200
    assert "已停用品項" in forecast
    assert "共 1 項" in forecast
    assert "去年業績合計" in forecast
    assert "10,000" in forecast
    assert 'data-item-status="active"' in forecast
    assert 'data-item-status="discontinued"' in forecast
    assert forecast.index("Product Active") < forecast.index("已停用品項") < forecast.index("Product Old")


def test_settings_page_uses_item_status_without_auxiliary_labels(monkeypatch):
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
                columns[8]: 0,
            }
        ]
    )
    monkeypatch.setattr(app, "load_sales_detail", lambda base_path, forecast_config: data)
    monkeypatch.setattr(operational_views, "load_sales_detail", lambda base_path, forecast_config: data)
    client = _client({"FORECAST_CONFIG": config, "DB_BASE_PATH": db_base_path})

    settings = client.get("/settings").get_data(as_text=True)

    assert 'name="item_status_P1"' in settings
    assert "使用中" in settings
    assert "停用" in settings
    assert "特殊品項" not in settings
    assert "新上市" not in settings
    assert "status_label_P1" not in settings


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
                columns[8]: 0,
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
    saved_settings = response.get_data(as_text=True)
    assert 'name="price_quantity_P1" type="number" min="0" step="1" value="100"' in saved_settings
    assert 'value="100.0"' not in saved_settings
    with sqlite3.connect(db_base_path / "mor_workbench.db") as conn:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(item_configs)")]
        saved = conn.execute("SELECT price_quantity FROM item_configs WHERE product_code = 'P1'").fetchone()
    assert "price_quantity" in columns
    assert saved == (100,)
    assert 'data-price-quantity="100' in forecast
    # Estimated amount is now computed client-side from data attributes
    assert 'data-price=' in forecast


def test_item_settings_save_clears_forecast_context_cache(monkeypatch):
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
                columns[6]: 100,
                columns[7]: 1000,
                columns[8]: 0,
            }
            for month in (1, 2, 3)
        ]
    )
    monkeypatch.setattr(app, "load_sales_detail", lambda base_path, forecast_config: data)
    monkeypatch.setattr(operational_views, "load_sales_detail", lambda base_path, forecast_config: data)
    client = _client({"FORECAST_CONFIG": config, "DB_BASE_PATH": db_base_path})

    first_forecast = client.get("/forecast?year=2026&month=4").get_data(as_text=True)
    response = client.post(
        "/items/save",
        data={
            "product_codes": ["P1"],
            "is_budgeted_P1": "1",
        },
    )
    second_forecast = client.get("/forecast?year=2026&month=4").get_data(as_text=True)

    assert "Product One" in first_forecast
    assert response.status_code == 200
    assert "Product One" not in second_forecast


def test_unbudgeted_item_has_no_budget_target_on_forecast_page(monkeypatch):
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
                columns[6]: 100,
                columns[7]: 1000,
                columns[8]: 0,
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

    response = client.post(
        "/items/save",
        data={
            "product_codes": ["P1"],
            "is_visible_P1": "1",
        },
    )
    forecast = client.get("/forecast?year=2026&month=4").get_data(as_text=True)

    assert response.status_code == 200
    assert 'data-budget="0.0"' in forecast


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
    assert re.search(r'name="manual_adjustment__[^"]+" type="number" min="0" step="1"', html)
    assert 'step="0.01"' not in html
    assert 'data-validation-message' in html
    assert "人工數量必須是 0 以上的數字" in html


def test_adjustment_save_manual_quantity_as_integer():
    db_base_path = _isolated_db_base()
    client = _client({"DB_BASE_PATH": db_base_path})

    response = client.post(
        "/adjustments/save",
        data={
            "row_id": "Hospital A__P1",
            "manual_adjustment": "12.7",
            "reason": "Review",
            "year": "2026",
            "month": "5",
        },
    )

    assert response.status_code == 200
    with sqlite3.connect(db_base_path / "mor_workbench.db") as conn:
        saved = conn.execute(
            """
            SELECT manual_quantity
            FROM forecast_adjustments
            WHERE year = 2026 AND month = 5 AND customer_name = 'Hospital A' AND product_code = 'P1'
            """
        ).fetchone()
    assert saved == (12,)


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


def test_forecast_row_keeps_three_char_abbreviation_except_eli_dose():
    row_template = Path("templates/_forecast_row.html").read_text(encoding="utf-8")
    css = Path("static/css/mor.css").read_text(encoding="utf-8")

    assert "product_display_name" in row_template
    assert "min-width: 96px;" in css


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


def test_forecast_detail_uses_neutral_zero_budget_status():
    js = Path("static/js/forecast-table.js").read_text(encoding="utf-8")

    assert "缺預算" in js
    assert "預算為 0" not in js


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
                columns[8]: 0,
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
                columns[5]: "ELI 22.5癌立佳",
                columns[6]: 100,
                columns[7]: 100,
                columns[8]: 0,
            },
            {
                columns[0]: 2026,
                columns[1]: 4,
                columns[2]: 10,
                columns[3]: "Hospital A",
                columns[4]: "P1",
                columns[5]: "ELI 22.5癌立佳",
                columns[6]: 40,
                columns[7]: 100,
                columns[8]: 0,
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
    assert "狀態" in html
    assert "去年成長率" in html
    assert "預算達成率" in html
    assert "週期狀態" in html
    assert "高風險" in html
    assert html.index("monitor-sticky--status") < html.index("monitor-sticky--customer")
    assert html.index("monitor-sticky--customer") < html.index("monitor-sticky--product")
    assert 'title="ELI 22.5癌立佳">ELI 22.5</td>' in html
    assert "ID: P1" not in html
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
                columns[8]: 0,
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
    assert "品項設定" in html
    assert "settings-workspace" in html
    assert "settings-health-panel" in html
    assert "儲存設定" in html


def test_dashboard_omits_zero_budget_notice_but_keeps_price_warning(monkeypatch):
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
                columns[8]: 0,
            }
        ]
    )
    monkeypatch.setattr(app, "load_sales_detail", lambda base_path, forecast_config: data)
    monkeypatch.setattr(operational_views, "load_sales_detail", lambda base_path, forecast_config: data)
    client = _client({"FORECAST_CONFIG": config, "DB_BASE_PATH": db_base_path})

    dashboard = client.get("/").get_data(as_text=True)
    settings = client.get("/settings").get_data(as_text=True)

    assert "有 1 筆缺少預算目標" not in dashboard
    assert "有 1 筆單價為 0" in dashboard
    assert "有 1 筆缺少預算目標" not in settings
    assert "有 1 筆單價為 0" not in settings


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
                columns[8]: 0,
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
                columns[8]: 0,
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


# ---------------------------------------------------------------------------
# Daily sales import route and upload UI
# ---------------------------------------------------------------------------

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
                columns[8]: 0,
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
                columns[8]: 0,
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


def test_product_monitor_page_exposes_daily_sales_import_form():
    client = _client()

    html = client.get("/monitor/products").get_data(as_text=True)

    assert 'action="/monitor/products/import"' in html
    assert 'name="daily_sales_file"' in html
    assert "選擇當月累積業績檔" in html
    assert "系統將依欄位格式判斷資料，不限制檔名。" in html
