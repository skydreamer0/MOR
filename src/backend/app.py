from __future__ import annotations

import hashlib
import logging
from datetime import date
from pathlib import Path

import pandas as pd
from flask import Flask, Response, redirect, render_template, request, send_file, url_for
from flask_caching import Cache

from src.backend.data_validator import validate_budget_coverage, validate_health
from src.backend.dashboard_analytics_workflow import build_dashboard_template_context
from src.backend.monthly_review import build_monthly_review, list_reviewable_months
from src.backend.monthly_review_actions import build_action_lists
from src.backend.monthly_review_chart import build_trend_chart
from src.backend.monthly_review_customers import build_customer_summary
from src.backend.monthly_review_export import export_monthly_review
from src.backend.monthly_review_forecast_bias import build_forecast_bias
from src.backend.monthly_review_products import build_product_summary
from src.backend.monthly_review_trend import build_trend
from src.backend.data_loader import default_target_from_data, default_target_from_db, latest_closed_month_from_data, load_sales_detail
from src.backend.exporter import export_forecast
from src.backend.forecast_config import ForecastConfig
from src.backend.forecast_export_workflow import prepare_export_summary
from src.backend.forecast_models import ForecastSummary
from src.backend.forecast_write_workflow import save_row_override
from src.backend.item_settings_workflow import build_item_config_payloads_from_form
from src.backend.product_monitor_workflow import build_product_monitor_template_context
from src.backend.operational_views import (
    aggregate_to_analytics,
    build_forecast_page_context,
    build_monthly_review_report,
    forecast_amount_total,
    last_year_amount_total,
    update_item_configs,
)
from src.backend.web.form_parser import FormValidationError, parse_manual_quantities, parse_target_period, validate_target_period
from src.backend.web.forecast_presenter import product_display_name
from src.backend.daily_sales_importer import (
    close_month,
    get_close_record,
    import_daily_sales_workbook,
)
from src.backend.database import get_db
from src.backend.etl import import_current_month, sync_excel_to_db
from src.backend.snapshot_service import (
    delete_snapshot,
    is_finalized,
    list_snapshots,
    load_snapshot_items,
    save_snapshot,
    serialize_forecast_rows_for_snapshot,
)


logger = logging.getLogger(__name__)

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
    cache = Cache(config={"CACHE_TYPE": "SimpleCache", "CACHE_DEFAULT_TIMEOUT": 0, "CACHE_THRESHOLD": 500})
    cache.init_app(app)
    app.jinja_env.filters["product_display_name"] = product_display_name

    # Version counters for cache invalidation — no DB queries on hot path.
    # _month_versions tracks per-(year, month) writes (adjustments, daily imports, close-month).
    # _global_version tracks writes that affect all months (sync, item config changes).
    _month_versions: dict[tuple[int, int], int] = {}
    _global_version: list[int] = [0]

    def _make_cache_key(year: int, month: int, as_of: date | None = None) -> str:
        key = (
            f"forecast-context:{year}:{month}"
            f":g{_global_version[0]}"
            f":m{_month_versions.get((year, month), 0)}"
        )
        if as_of is not None:
            key += f":d{as_of.isoformat()}"
        return key

    def _invalidate_context_cache(year: int, month: int) -> None:
        _month_versions[(year, month)] = _month_versions.get((year, month), 0) + 1

    def _invalidate_all_context_cache() -> None:
        _global_version[0] += 1

    def _build_cached_context(year: int, month: int):
        today = date.today()
        as_of = today if (year, month) == (today.year, today.month) else None
        key = _make_cache_key(year, month, as_of)
        context = cache.get(key)
        if context is None:
            context = build_forecast_page_context(
                data_base_path,
                forecast_config,
                db,
                {"year": str(year), "month": str(month)},
                today=today,
            )
            cache.set(key, context)
        return context

    def _load_context_from_request():
        default_target = default_target_from_db(db)
        target = parse_target_period(request.args, default_target)
        return _build_cached_context(target.year, target.month)

    def _save_row_override(row_id: str, manual_qty: str | None, reason: str | None, year: int, month: int) -> None:
        save_row_override(db, row_id, manual_qty, reason, year, month)
        _invalidate_context_cache(year, month)

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

        template_context = build_dashboard_template_context(context) if context else {
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
            template_context = build_dashboard_template_context(context)
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
        try:
            validate_target_period(year, month)
        except FormValidationError:
            return Response("Invalid year/month range", status=400)
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
            context = _load_context_from_request()
            error_message = None
        except (FileNotFoundError, ValueError, FormValidationError) as exc:
            context = None
            error_message = f"無法產生跳單監控：{exc}"

        year = context.target.year if context else request.args.get("year", type=int) or 0
        month = context.target.month if context else request.args.get("month", type=int) or 0
        return render_template(
            "product_monitor.html",
            **build_product_monitor_template_context(
                context,
                db,
                fallback_year=year,
                fallback_month=month,
                error_message=error_message,
                import_message=request.args.get("import_message"),
                import_error=request.args.get("import_error"),
            ),
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
            snapshot_rows = serialize_forecast_rows_for_snapshot(ctx.summary.rows)
        except Exception as exc:
            logger.error("結月快照自動建立失敗 %d/%02d: %s", year, month, exc, exc_info=True)
            raise
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
            validate_target_period(year, month)
        except FormValidationError:
            return redirect(url_for("product_monitor", import_error="年月範圍不合法。"))
        try:
            snapshot_id = _find_or_create_close_snapshot(year, month)
            close_month(db, year, month, snapshot_id=snapshot_id, note=note)
            _invalidate_context_cache(year, month)
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
            _invalidate_context_cache(result.sales_year, result.sales_month)
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
            default_target = default_target_from_db(db)
            target = parse_target_period(request.form, default_target)

            context = build_forecast_page_context(
                data_base_path,
                forecast_config,
                db,
                {"year": str(target.year), "month": str(target.month)},
            )
            summary = context.summary
            manual_adjustments = parse_manual_quantities(request.form, key_prefix="manual_adjustment__", type_cast=int)
            adjustment_reasons = parse_manual_quantities(request.form, key_prefix="adjustment_reason__", type_cast=str)

            _validate_submitted_row_ids(summary, set(manual_adjustments))
            _validate_forecast_signature(summary, request.form.get("forecast_signature", ""))

            summary = prepare_export_summary(summary, manual_adjustments, adjustment_reasons)
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

    @app.get("/customers")
    def customers() -> str:
        try:
            context = _load_context_from_request()
            slices = aggregate_to_analytics(context.summary.rows, "customer", context.target)
            year, month = context.target.year, context.target.month
            error_message = None
        except (FileNotFoundError, ValueError, FormValidationError) as exc:
            slices = []
            year = request.args.get("year", "")
            month = request.args.get("month", "")
            error_message = f"無法載入客戶分析：{exc}"
        return render_template(
            "customers.html",
            slices=slices,
            year=year,
            month=month,
            error_message=error_message,
        )

    @app.get("/settings")
    def settings() -> str:
        try:
            context = build_forecast_page_context(data_base_path, forecast_config, db, request.args)
            items = context.items
            health = context.health
            data_issues = validate_health(health)
            with db.get_connection() as conn:
                budget_rows = conn.execute(
                    "SELECT DISTINCT product_code FROM budget_targets WHERE year = ?",
                    (context.target.year,),
                ).fetchall()
            budget_codes = {r["product_code"] for r in budget_rows}
            sales_codes = {item["product_code"] for item in items}
            data_issues += validate_budget_coverage(sales_codes, budget_codes)
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
        action_lists = None
        customer_summary = None
        product_summary = None
        forecast_bias = None
        trend_chart = None
        error_message = None
        if year and month:
            try:
                summary = build_monthly_review(db, year, month)
                action_lists = build_action_lists(db, year, month)
                customer_summary = build_customer_summary(db, year, month)
                product_summary = build_product_summary(db, year, month)
                forecast_bias = build_forecast_bias(db, year, month)
                trend_chart = build_trend_chart(build_trend(db, year, month))
            except (ValueError, LookupError, KeyError, TypeError) as exc:
                error_message = str(exc)
        return render_template(
            "monthly_review.html",
            year=year,
            month=month,
            summary=summary,
            action_lists=action_lists,
            customer_summary=customer_summary,
            product_summary=product_summary,
            forecast_bias=forecast_bias,
            trend_chart=trend_chart,
            reviewable_months=reviewable,
            error_message=error_message,
        )

    @app.get("/monthly-review/export.xlsx")
    def monthly_review_export() -> Response:
        year  = request.args.get("year",  type=int)
        month = request.args.get("month", type=int)
        if not (year and month):
            return Response("missing year/month", status=400)
        try:
            summary = build_monthly_review(db, year, month)
        except Exception as exc:
            return Response(str(exc), status=400)
        wb = export_monthly_review(
            summary,
            actions=build_action_lists(db, year, month),
            customers=build_customer_summary(db, year, month),
            products=build_product_summary(db, year, month),
            bias=build_forecast_bias(db, year, month),
            trend=build_trend(db, year, month),
        )
        filename = f"monthly_review_{year}-{month:02d}.xlsx"
        return Response(
            wb.getvalue(),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    @app.get("/items")
    def items_management() -> Response:
        return redirect(url_for("settings"))

    @app.post("/items/save")
    def save_items() -> Response:
        items = build_item_config_payloads_from_form(request.form)
        update_item_configs(db, items)
        _invalidate_all_context_cache()
        return redirect(url_for("settings"))

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
            _invalidate_all_context_cache()
            return "資料同步完成！請重新載入工作台。"
        except Exception as exc:
            return f"同步失敗：{exc}"

    @app.post("/upload/current-month")
    def upload_current_month() -> str:
        """接收 SHPB 出貨報表，寫入 current_month_records。

        上傳後清除 cache，讓下次頁面請求重新合併當月資料。
        支援重複上傳：每次只取代 SHPB 涵蓋的年月，歷史資料不受影響。
        """
        file = request.files.get("file")
        if not file or not file.filename:
            return "請選擇檔案", 400
        try:
            df = pd.read_excel(file)
            count = import_current_month(db, df)
            _invalidate_all_context_cache()
            return f"已匯入 {count} 筆當月業績資料。"
        except Exception as exc:
            return f"匯入失敗：{exc}", 400

    @app.post("/adjustments/save")
    def save_adjustment() -> Response:
        row_id = request.form.get("row_id")
        manual_qty = request.form.get("manual_adjustment")
        reason = request.form.get("reason")
        year = request.form.get("year", type=int)
        month = request.form.get("month", type=int)

        if not row_id or year is None or month is None:
            return Response("Missing required fields", status=400)
        try:
            validate_target_period(year, month)
        except FormValidationError:
            return Response("Invalid year/month range", status=400)

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
        try:
            validate_target_period(year, month)
        except FormValidationError:
            return Response("Invalid year/month range", status=400)
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

            snapshot_rows = serialize_forecast_rows_for_snapshot(summary.rows)
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
