from __future__ import annotations

import calendar
import hashlib
import os
from dataclasses import replace
from datetime import date
from pathlib import Path

from flask import Flask, Response, redirect, render_template, request, send_file, url_for
from flask_caching import Cache

from src.backend.data_validator import validate_health
from src.backend.monthly_review import build_monthly_review, list_reviewable_months
from src.backend.data_loader import default_target_from_data, load_sales_detail, normalize_product_code
from src.backend.exporter import export_forecast
from src.backend.forecast_config import ForecastConfig
from src.backend.forecast_engine import apply_user_adjustments
from src.backend.forecast_models import ForecastSummary
from src.backend.operational_views import (
    aggregate_to_analytics,
    build_customer_risk_ranking,
    build_forecast_page_context,
    forecast_amount_total,
    last_year_amount_total,
    recalculate_forecast_amounts,
    build_status_distribution,
)
from src.backend.web.form_parser import FormValidationError, parse_manual_quantities, parse_target_period
from src.backend.web.forecast_presenter import product_display_name
from src.backend.daily_sales_importer import (
    close_month,
    get_close_record,
    get_latest_import_batch,
    import_daily_sales_workbook,
)
from src.backend.database import get_db
from src.backend.etl import sync_excel_to_db
from src.backend.snapshot_service import (
    delete_snapshot,
    is_finalized,
    list_snapshots,
    load_snapshot_items,
    save_snapshot,
)


BASE_PATH = Path(__file__).resolve().parent


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def create_app(config: dict | None = None) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(PROJECT_ROOT / "templates"),
        static_folder=str(PROJECT_ROOT / "static"),
    )
    app.config.update(config or {})
    forecast_config = app.config.get("FORECAST_CONFIG", ForecastConfig())
    data_base_path = Path(app.config.get("DATA_BASE_PATH", PROJECT_ROOT))
    db_base_path = Path(app.config.get("DB_BASE_PATH", PROJECT_ROOT))
    db = get_db(db_base_path)
    cache = Cache(config={"CACHE_TYPE": "SimpleCache", "CACHE_DEFAULT_TIMEOUT": 0})
    cache.init_app(app)
    app.jinja_env.filters["product_display_name"] = product_display_name

    def _make_cache_key(year: int, month: int) -> str:
        detail_path = data_base_path / forecast_config.detail_file
        try:
            mtime = int(os.path.getmtime(detail_path))
        except FileNotFoundError:
            mtime = 0
        return f"forecast-context:{mtime}:{year}:{month}"

    def _build_cached_context(year: int, month: int):
        key = _make_cache_key(year, month)
        context = cache.get(key)
        if context is None:
            context = build_forecast_page_context(
                data_base_path,
                forecast_config,
                db,
                {"year": str(year), "month": str(month)},
            )
            cache.set(key, context)
        return context

    def _load_context_from_request():
        data = load_sales_detail(data_base_path, forecast_config)
        default_target = default_target_from_data(data, forecast_config)
        target = parse_target_period(request.args, default_target)
        return _build_cached_context(target.year, target.month)

    def _dashboard_template_context(context) -> dict:
        remaining_days = 0
        today = date.today()
        t_year, t_month = context.target.year, context.target.month
        _, last_day = calendar.monthrange(t_year, t_month)
        month_end = date(t_year, t_month, last_day)
        month_start = date(t_year, t_month, 1)
        if today > month_end:
            remaining_days = 0
        elif today < month_start:
            remaining_days = last_day
        else:
            remaining_days = (month_end - today).days

        all_monitor = context.monitor_rows
        status_dist = build_status_distribution(all_monitor)
        customer_ranking = build_customer_risk_ranking(all_monitor)
        high_risk_rows = [row for row in all_monitor if row.status_key == "high"]
        high_risk_rows.sort(key=lambda r: r.amount_impact)

        rows = context.summary.rows
        target = context.target
        return {
            "year": target.year,
            "month": target.month,
            "metrics": context.dashboard,
            "health": context.health,
            "monitor_rows": high_risk_rows[:15],
            "remaining_days": remaining_days,
            "status_dist": status_dist,
            "customer_ranking": customer_ranking,
            "data_issues": validate_health(context.health),
            "analytics_total":     aggregate_to_analytics(rows, "total",    target),
            "analytics_customers": aggregate_to_analytics(rows, "customer", target),
            "analytics_products":  aggregate_to_analytics(rows, "product",  target),
        }

    def _save_row_override(row_id: str, manual_qty: str | None, reason: str | None, year: int, month: int) -> None:
        customer, product_code = row_id.split("__", 1)
        try:
            val = int(float(manual_qty)) if manual_qty and manual_qty.strip() else None
        except ValueError as exc:
            raise FormValidationError("Invalid quantity") from exc

        with db.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO forecast_adjustments
                (year, month, customer_name, product_code, manual_quantity, adjustment_reason, updated_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (year, month, customer, product_code, val, reason, "User"),
            )
            conn.commit()
        cache.clear()

    def _find_forecast_row(row_id: str, year: int, month: int):
        context = _build_cached_context(year, month)
        for row in context.summary.rows:
            if row.row_id == row_id:
                return row
        raise FormValidationError(f"Unknown forecast row: {row_id}")

    def _forecast_row_risk(row) -> str:
        if row.last_year_same_month_qty > 0 and row.final_forecast < row.last_year_same_month_qty * 0.9:
            return "high"
        return "normal"

    def _risk_levels(rows) -> dict[str, str]:
        return {row.row_id: _forecast_row_risk(row) for row in rows}

    @app.get("/")
    def dashboard() -> str:
        try:
            context = _load_context_from_request()
            error_message = None
        except (FileNotFoundError, ValueError, FormValidationError) as exc:
            context = None
            error_message = f"無法產生預估：{exc}"

        template_context = _dashboard_template_context(context) if context else {
            "year": request.args.get("year", ""),
            "month": request.args.get("month", ""),
            "metrics": None,
            "health": None,
            "monitor_rows": [],
            "remaining_days": 0,
            "status_dist": {},
            "customer_ranking": [],
            "data_issues": [],
            "analytics_total": [],
            "analytics_customers": [],
            "analytics_products": [],
        }
        return render_template(
            "index.html",
            error_message=error_message,
            **template_context,
        )

    @app.get("/dashboard/metrics")
    def dashboard_metrics() -> str:
        try:
            context = _load_context_from_request()
            template_context = _dashboard_template_context(context)
        except (FileNotFoundError, ValueError, FormValidationError) as exc:
            return Response(f"無法更新預估：{exc}", status=400, mimetype="text/plain; charset=utf-8")
        return render_template("_dashboard_metrics.html", **template_context)

    @app.get("/forecast")
    def forecast() -> str:
        try:
            context = _load_context_from_request()
            summary = context.summary
            error_message = None
        except (FileNotFoundError, ValueError, FormValidationError) as exc:
            summary = None
            error_message = f"無法產生預估：{exc}"

        rows = summary.rows if summary else []
        sorted_rows = sorted(rows, key=lambda row: (0 if _forecast_row_risk(row) == "high" else 1, row.customer, row.product_code))
        active_rows = [row for row in sorted_rows if row.item_status != "discontinued"]
        discontinued_rows = [row for row in sorted_rows if row.item_status == "discontinued"]
        visible_rows = active_rows[: forecast_config.visible_row_limit]
        rendered_rows = visible_rows + discontinued_rows
        visible_total = forecast_amount_total(visible_rows)
        unrendered_total = (summary.total if summary else 0) - visible_total
        customers = sorted({row.customer for row in visible_rows})
        return render_template(
            "forecast.html",
            year=summary.year if summary else request.args.get("year", ""),
            month=summary.month if summary else request.args.get("month", ""),
            rows=visible_rows,
            discontinued_rows=discontinued_rows,
            discontinued_last_year_total=last_year_amount_total(discontinued_rows),
            total=summary.total if summary else 0,
            unrendered_total=unrendered_total,
            forecast_signature=_forecast_signature(summary) if summary else "",
            row_count=len(rows),
            shown_count=len(rendered_rows),
            error_message=error_message,
            is_finalized=is_finalized(db, summary.year, summary.month) if summary else False,
            snapshots=list_snapshots(db, summary.year, summary.month) if summary else [],
            customers=customers,
            risk_levels=_risk_levels(rendered_rows),
        )

    @app.patch("/forecast/row/<path:row_id>")
    def patch_forecast_row(row_id: str) -> str | Response:
        year = request.form.get("year", type=int)
        month = request.form.get("month", type=int)
        if year is None or month is None:
            return Response("Missing year/month", status=400)
        reason = request.form.get("note", request.form.get(f"adjustment_reason__{row_id}", ""))
        try:
            qty = request.form.get("qty", request.form.get(f"manual_adjustment__{row_id}"))
            _save_row_override(row_id, qty, reason, year, month)
            row = _find_forecast_row(row_id, year, month)
        except FormValidationError as exc:
            return Response(str(exc), status=400)
        return render_template(
            "_forecast_row.html",
            row=row,
            year=year,
            month=month,
            risk_levels={row.row_id: _forecast_row_risk(row)},
        )

    @app.get("/monitor/products")
    def product_monitor() -> str:
        try:
            context = build_forecast_page_context(data_base_path, forecast_config, db, request.args)
            error_message = None
        except (FileNotFoundError, ValueError, FormValidationError) as exc:
            context = None
            error_message = f"無法產生跳單監控：{exc}"

        year = context.target.year if context else request.args.get("year", type=int) or 0
        month = context.target.month if context else request.args.get("month", type=int) or 0
        return render_template(
            "product_monitor.html",
            year=year,
            month=month,
            rows=context.monitor_rows if context else [],
            error_message=error_message,
            import_message=request.args.get("import_message"),
            import_error=request.args.get("import_error"),
            latest_batch=get_latest_import_batch(db, year, month) if year and month else None,
            close_record=get_close_record(db, year, month) if year and month else None,
        )

    def _find_or_create_close_snapshot(year: int, month: int) -> int | None:
        """Return an existing Final/CloseMonth snapshot ID, or auto-create one."""
        with db.get_connection() as conn:
            row = conn.execute(
                """
                SELECT id FROM forecast_snapshots
                WHERE year = ? AND month = ? AND snapshot_type IN ('Final', 'CloseMonth')
                ORDER BY id DESC LIMIT 1
                """,
                (year, month),
            ).fetchone()
        if row:
            return row["id"]
        # Auto-create from current forecast state
        try:
            ctx = build_forecast_page_context(
                data_base_path, forecast_config, db,
                {"year": str(year), "month": str(month)},
            )
            snapshot_rows = [
                {
                    "customer_name": r.customer,
                    "product_code": r.product_code,
                    "system_forecast": r.system_forecast,
                    "manual_adjustment": r.manual_adjustment,
                    "final_forecast": r.final_forecast,
                }
                for r in ctx.summary.rows
            ]
        except Exception:
            snapshot_rows = []
        return save_snapshot(
            db, year, month,
            f"結月快照 {year}/{month:02d}", "CloseMonth",
            snapshot_rows, created_by="結月",
        )

    @app.post("/monitor/products/close-month")
    def close_product_monitor_month() -> Response:
        year = request.form.get("year", type=int)
        month = request.form.get("month", type=int)
        note = request.form.get("note", "").strip() or None
        if not year or not month:
            return redirect(url_for("product_monitor", import_error="缺少年月資訊。"))
        try:
            snapshot_id = _find_or_create_close_snapshot(year, month)
            close_month(db, year, month, snapshot_id=snapshot_id, note=note)
            cache.clear()
        except Exception as exc:
            return redirect(url_for("product_monitor", year=year, month=month,
                                    import_error=f"結月失敗：{exc}"))
        return redirect(url_for("product_monitor", year=year, month=month,
                                import_message=f"{year}/{month:02d} 結月完成。"))

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

    @app.post("/export")
    def export() -> Response:
        try:
            data = load_sales_detail(data_base_path, forecast_config)
            default_target = default_target_from_data(data, forecast_config)
            target = parse_target_period(request.form, default_target)

            context = build_forecast_page_context(
                data_base_path,
                forecast_config,
                db,
                {"year": str(target.year), "month": str(target.month)},
            )
            summary = context.summary
            manual_adjustments = parse_manual_quantities(request.form, key_prefix="manual_adjustment__", type_cast=int)
            legacy_manual_adjustments = parse_manual_quantities(request.form, type_cast=int)
            manual_adjustments = {**legacy_manual_adjustments, **manual_adjustments}
            adjustment_reasons = parse_manual_quantities(request.form, key_prefix="adjustment_reason__", type_cast=str)

            _validate_submitted_row_ids(summary, set(manual_adjustments))
            _validate_forecast_signature(summary, request.form.get("forecast_signature", ""))

            summary = apply_user_adjustments(
                summary,
                manual_adjustments=manual_adjustments,
                excluded_ids=set(),
            )
            rows = [
                replace(row, adjustment_reason=adjustment_reasons.get(row.row_id, row.adjustment_reason))
                for row in summary.rows
            ]
            rows = recalculate_forecast_amounts(rows)
            summary = replace(summary, rows=rows, total=forecast_amount_total(rows))
        except (FileNotFoundError, ValueError, FormValidationError) as exc:
            return Response(f"無法匯出預估：{exc}", status=400, mimetype="text/plain; charset=utf-8")

        output = export_forecast(summary)
        filename = f"業績預估_{summary.year}{summary.month:02d}.xlsx"
        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @app.get("/settings")
    def settings() -> str:
        try:
            context = build_forecast_page_context(data_base_path, forecast_config, db, request.args)
            items = context.items
            health = context.health
            data_issues = validate_health(health)
            error_message = None
        except (FileNotFoundError, ValueError, FormValidationError) as exc:
            context = None
            items = []
            health = None
            data_issues = []
            error_message = f"載入系統設定失敗：{exc}"

        return render_template(
            "settings.html",
            items=items,
            health=health,
            data_issues=data_issues,
            year=context.target.year if context else request.args.get("year", ""),
            month=context.target.month if context else request.args.get("month", ""),
            error_message=error_message,
        )

    @app.get("/monthly-review")
    def monthly_review() -> str:
        reviewable = list_reviewable_months(db)
        year  = request.args.get("year",  type=int) or (reviewable[0][0] if reviewable else 0)
        month = request.args.get("month", type=int) or (reviewable[0][1] if reviewable else 0)
        summary = None
        error_message = None
        if year and month:
            try:
                summary = build_monthly_review(db, year, month)
            except (ValueError, Exception) as exc:
                error_message = str(exc)
        return render_template(
            "monthly_review.html",
            year=year,
            month=month,
            summary=summary,
            reviewable_months=reviewable,
            error_message=error_message,
        )

    @app.get("/items")
    def items_management() -> Response:
        return redirect(url_for("settings"))

    @app.post("/items/save")
    def save_items() -> Response:
        product_codes = request.form.getlist("product_codes")
        with db.get_connection() as conn:
            for pid in product_codes:
                pid = normalize_product_code(pid)
                is_excluded = 1 if request.form.get(f"is_excluded_{pid}") == "1" else 0
                is_budgeted = 1 if request.form.get(f"is_budgeted_{pid}") == "1" else 0
                is_visible = 1 if request.form.get(f"is_visible_{pid}") == "1" else 0
                try:
                    price_quantity = int(float(request.form.get(f"price_quantity_{pid}") or 0))
                except ValueError:
                    price_quantity = 0
                item_status = request.form.get(f"item_status_{pid}")
                if item_status not in {"active", "discontinued"}:
                    item_status = "active"
                
                conn.execute("""
                    INSERT OR IGNORE INTO item_configs
                    (product_code, is_excluded, is_budgeted, is_visible, price_quantity, item_status, status_label, custom_category)
                    VALUES (?, 0, 1, 1, 0, 'active', NULL, NULL)
                """, (pid,))
                conn.execute("""
                    UPDATE item_configs
                    SET is_excluded = ?, is_budgeted = ?, is_visible = ?, price_quantity = ?, item_status = ?
                    WHERE product_code = ?
                """, (is_excluded, is_budgeted, is_visible, price_quantity, item_status, pid))
            conn.commit()
        cache.clear()
        return settings()

    @app.get("/exclusions")
    def exclusions_management() -> str:
        return redirect(url_for("settings"))

    @app.post("/exclusions/save")
    def save_exclusions() -> Response:
        return redirect(url_for("settings"))

    @app.post("/sync")
    def sync_data() -> str:
        try:
            sync_excel_to_db(db, data_base_path)
            return "資料同步完成！請重新載入工作台。"
        except Exception as exc:
            return f"同步失敗：{exc}"

    @app.post("/adjustments/save")
    def save_adjustment() -> Response:
        row_id = request.form.get("row_id")
        manual_qty = request.form.get("manual_adjustment")
        reason = request.form.get("reason")
        year = request.form.get("year", type=int)
        month = request.form.get("month", type=int)

        if not row_id or year is None or month is None:
            return Response("Missing required fields", status=400)

        # Parse row_id back to customer/product if needed, but it's easier to store as is 
        # or use the year/month/customer/product key.
        # Our row_id is currently "{customer}__{product_code}"
        try:
            _save_row_override(row_id, manual_qty, reason, year, month)
        except FormValidationError:
            return Response("Invalid quantity", status=400)
        
        return Response("Saved", status=200)

    @app.post("/snapshots/save")
    def save_snapshot_route() -> Response:
        year = request.form.get("year", type=int)
        month = request.form.get("month", type=int)
        snapshot_name = request.form.get("snapshot_name", "").strip()
        snapshot_type = request.form.get("snapshot_type", "Draft")

        if not year or not month:
            return Response("Missing year/month", status=400)
        if not snapshot_name:
            snapshot_name = f"{'定稿' if snapshot_type == 'Final' else '草稿'} {year}/{month:02d}"

        try:
            context = build_forecast_page_context(
                data_base_path,
                forecast_config,
                db,
                {"year": str(year), "month": str(month)},
            )
            summary = context.summary

            snapshot_rows = [
                {
                    "customer_name": r.customer,
                    "product_code": r.product_code,
                    "system_forecast": r.system_forecast,
                    "manual_adjustment": r.manual_adjustment,
                    "final_forecast": r.final_forecast,
                }
                for r in summary.rows
            ]
            snapshot_id = save_snapshot(db, year, month, snapshot_name, snapshot_type, snapshot_rows)
            return redirect(url_for("forecast", year=year, month=month))
        except ValueError as exc:
            return Response(str(exc), status=400)
        except Exception as exc:
            return Response(f"快照儲存失敗：{exc}", status=500)

    @app.post("/snapshots/delete")
    def delete_snapshot_route() -> Response:
        snapshot_id = request.form.get("snapshot_id", type=int)
        year = request.form.get("year", type=int)
        month = request.form.get("month", type=int)
        if not snapshot_id:
            return Response("Missing snapshot_id", status=400)
        try:
            delete_snapshot(db, snapshot_id)
        except ValueError as exc:
            return Response(str(exc), status=400)
        return redirect(url_for("forecast", year=year, month=month))

    return app


def _load_items_from_sales(data_base_path: Path, forecast_config: ForecastConfig, db) -> list[dict]:
    data = load_sales_detail(data_base_path, forecast_config)
    unique_products = data[["商品號", "商品簡稱"]].drop_duplicates("商品號")

    item_configs = _load_item_configs(db)
    items = []
    for _, row in unique_products.iterrows():
        pid = normalize_product_code(row["商品號"])
        cfg = item_configs.get(pid, {
            "is_excluded": False,
            "is_budgeted": True,
            "is_visible": True,
            "price_quantity": 0.0,
            "item_status": "active",
        })
        items.append({
            "product_code": pid,
            "product_name": row["商品簡稱"],
            **cfg,
        })
    return items


def _load_item_configs(db) -> dict[str, dict]:
    with db.get_connection() as conn:
        rows = conn.execute("SELECT * FROM item_configs").fetchall()
        configs = {
            row["product_code"]: {
                "is_excluded": bool(row["is_excluded"]),
                "is_budgeted": bool(row["is_budgeted"]),
                "is_visible": bool(row["is_visible"]),
                "price_quantity": float(row["price_quantity"] or 0),
                "item_status": "discontinued" if row["item_status"] == "discontinued" or row["status_label"] == "停用" else "active",
            }
            for row in rows
        }
        for row in rows:
            normalized_code = normalize_product_code(row["product_code"])
            configs.setdefault(normalized_code, configs[row["product_code"]])
        return configs


def _load_adjustments(db, year: int, month: int) -> tuple[dict[str, float], dict[str, str]]:
    manual_adjustments = {}
    adjustment_reasons = {}
    with db.get_connection() as conn:
        rows = conn.execute("""
            SELECT customer_name, product_code, manual_quantity, adjustment_reason 
            FROM forecast_adjustments 
            WHERE year = ? AND month = ?
        """, (year, month)).fetchall()
        for row in rows:
            row_id = f"{row['customer_name']}__{row['product_code']}"
            if row["manual_quantity"] is not None:
                manual_adjustments[row_id] = row["manual_quantity"]
            if row["adjustment_reason"]:
                adjustment_reasons[row_id] = row["adjustment_reason"]
    return manual_adjustments, adjustment_reasons


def _load_exclusions(db) -> set[str]:
    with db.get_connection() as conn:
        rows = conn.execute(
            "SELECT product_code FROM item_configs WHERE is_excluded = 1"
        ).fetchall()
    excluded = set()
    for row in rows:
        product_code = row["product_code"]
        excluded.add(product_code)
        excluded.add(normalize_product_code(product_code))
    return excluded


def _load_budgets(db, year: int, month: int) -> dict[str, float]:
    budgets = {}
    with db.get_connection() as conn:
        rows = conn.execute("""
            SELECT customer_name, product_code, target_quantity
            FROM budget_targets
            WHERE year = ? AND month = ?
        """, (year, month)).fetchall()
        for row in rows:
            row_id = f"{row['customer_name']}__{row['product_code']}"
            budgets[row_id] = row["target_quantity"]
    return budgets


def _validate_submitted_row_ids(summary: ForecastSummary, submitted_row_ids: set[str]) -> None:
    known_row_ids = {row.row_id for row in summary.rows}
    unknown_row_ids = sorted(submitted_row_ids - known_row_ids)
    if unknown_row_ids:
        raise FormValidationError(f"Unknown forecast row: {', '.join(unknown_row_ids)}")


def _validate_forecast_signature(summary: ForecastSummary, submitted_signature: object) -> None:
    if not submitted_signature:
        return
    if str(submitted_signature) != _forecast_signature(summary):
        raise FormValidationError("Forecast review changed. Reload the page before exporting.")


def _forecast_signature(summary: ForecastSummary) -> str:
    lines = [f"{summary.year}-{summary.month:02d}"]
    for row in summary.rows:
        lines.append(
            "|".join(
                [
                    row.row_id,
                    f"{row.system_forecast:.8f}",
                    f"{row.latest_price:.8f}",
                    f"{row.estimated_amount:.8f}",
                    row.forecast_basis,
                ]
            )
        )
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
