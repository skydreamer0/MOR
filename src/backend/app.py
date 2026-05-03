from __future__ import annotations

import hashlib
from pathlib import Path

from flask import Flask, Response, render_template, request, send_file

from src.backend.data_loader import default_target_from_data, load_sales_detail
from src.backend.exporter import export_forecast
from src.backend.forecast_config import ForecastConfig
from src.backend.forecast_engine import ForecastOptions, apply_user_adjustments, build_forecast
from src.backend.forecast_models import ForecastSummary
from src.backend.web.form_parser import FormValidationError, parse_excluded_ids, parse_manual_quantities, parse_target_period
from src.backend.database import get_db
from src.backend.etl import sync_excel_to_db
from src.backend.history_service import enrich_rows_with_history
import json


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

    @app.get("/")
    def index() -> str:
        try:
            data = load_sales_detail(data_base_path, forecast_config)
            target = default_target_from_data(data, forecast_config)
            target = parse_target_period(request.args, target)
            
            item_configs = _load_item_configs(db)
            excluded_item_ids = {pid for pid, cfg in item_configs.items() if cfg['is_excluded']}
            manual_adjustments, adjustment_reasons = _load_adjustments(db, target.year, target.month)
            budget_targets = _load_budgets(db, target.year, target.month)
            
            summary = build_forecast(
                data,
                target,
                ForecastOptions(
                    include_all=True, 
                    max_cycle_interval_days=forecast_config.max_cycle_interval_days,
                    excluded_item_ids=excluded_item_ids
                ),
                forecast_config,
            )
            # Filter by visibility
            from dataclasses import replace
            filtered_rows = [row for row in summary.rows if item_configs.get(row.product_code, {}).get('is_visible', True)]
            summary = replace(
                summary,
                rows=filtered_rows,
                total=sum(row.estimated_amount for row in filtered_rows if not row.excluded),
            )
            
            # Enrich with historical trends (batch SQL — Phase 2 Data Engine)
            enriched_rows = enrich_rows_with_history(summary.rows, db, target.year, target.month)
            summary = replace(summary, rows=enriched_rows)
            
            # Apply adjustments and budgets
            summary = apply_user_adjustments(
                summary,
                manual_adjustments=manual_adjustments,
                excluded_ids=set(),
            )
            
            for row in summary.rows:
                # Apply reasons
                new_reason = adjustment_reasons.get(row.row_id, row.adjustment_reason)
                # Apply budget
                new_budget = budget_targets.get(row.row_id, 0.0)
                
                from dataclasses import replace
                idx = summary.rows.index(row)
                summary.rows[idx] = replace(row, adjustment_reason=new_reason, budget_quantity=new_budget)
            
            error_message = None
        except (FileNotFoundError, ValueError, FormValidationError) as exc:
            summary = None
            error_message = f"無法產生預估：{exc}"

        rows = summary.rows if summary else []
        visible_rows = rows[: forecast_config.visible_row_limit]
        visible_total = sum(row.estimated_amount for row in visible_rows if not row.excluded)
        unrendered_total = (summary.total if summary else 0) - visible_total
        return render_template(
            "index.html",
            year=summary.year if summary else request.args.get("year", ""),
            month=summary.month if summary else request.args.get("month", ""),
            rows=visible_rows,
            total=summary.total if summary else 0,
            unrendered_total=unrendered_total,
            forecast_signature=_forecast_signature(summary) if summary else "",
            row_count=len(rows),
            shown_count=len(visible_rows),
            error_message=error_message,
        )

    @app.post("/export")
    def export() -> Response:
        try:
            data = load_sales_detail(data_base_path, forecast_config)
            default_target = default_target_from_data(data, forecast_config)
            target = parse_target_period(request.form, default_target)
            
            excluded_item_ids = _load_exclusions(db)
            
            summary = build_forecast(
                data,
                target,
                ForecastOptions(
                    include_all=True, 
                    max_cycle_interval_days=forecast_config.max_cycle_interval_days,
                    excluded_item_ids=excluded_item_ids
                ),
                forecast_config,
            )
            manual_adjustments = parse_manual_quantities(request.form, key_prefix="manual_adjustment__")
            legacy_manual_adjustments = parse_manual_quantities(request.form)
            manual_adjustments = {**legacy_manual_adjustments, **manual_adjustments}
            adjustment_reasons = parse_manual_quantities(request.form, key_prefix="adjustment_reason__", type_cast=str)
            
            # Global exclusions are already applied in build_forecast as 'excluded=True'
            _validate_submitted_row_ids(summary, set(manual_adjustments))
            _validate_forecast_signature(summary, request.form.get("forecast_signature", ""))
            
            # Need to update apply_user_adjustments signature to accept reasons too
            summary = apply_user_adjustments(
                summary,
                manual_adjustments=manual_adjustments,
                excluded_ids=set(), # Row-level exclusion removed
            )
            # Add reasons to rows (could be integrated into apply_user_adjustments)
            for row in summary.rows:
                if row.row_id in adjustment_reasons:
                    # Using replace to update reason
                    from dataclasses import replace
                    idx = summary.rows.index(row)
                    summary.rows[idx] = replace(row, adjustment_reason=adjustment_reasons[row.row_id])
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

    @app.get("/items")
    def items_management() -> str:
        try:
            data = load_sales_detail(data_base_path, forecast_config)
            # Get unique products from sales data
            unique_products = data[["商品號", "商品簡稱"]].drop_duplicates("商品號")
            
            item_configs = _load_item_configs(db)
            
            items = []
            for _, row in unique_products.iterrows():
                pid = str(row["商品號"])
                cfg = item_configs.get(pid, {
                    "is_excluded": False, 
                    "is_budgeted": True, 
                    "is_visible": True, 
                    "status_label": ""
                })
                items.append({
                    "product_code": pid,
                    "product_name": row["商品簡稱"],
                    **cfg
                })
            
            return render_template("items.html", items=items)
        except Exception as exc:
            return f"載入品項管理失敗：{exc}"

    @app.post("/items/save")
    def save_items() -> Response:
        product_codes = request.form.getlist("product_codes")
        with db.get_connection() as conn:
            for pid in product_codes:
                is_excluded = 1 if request.form.get(f"is_excluded_{pid}") == "1" else 0
                is_budgeted = 1 if request.form.get(f"is_budgeted_{pid}") == "1" else 0
                is_visible = 1 if request.form.get(f"is_visible_{pid}") == "1" else 0
                status_label = request.form.get(f"status_label_{pid}")
                
                conn.execute("""
                    INSERT OR REPLACE INTO item_configs 
                    (product_code, is_excluded, is_budgeted, is_visible, status_label)
                    VALUES (?, ?, ?, ?, ?)
                """, (pid, is_excluded, is_budgeted, is_visible, status_label))
            conn.commit()
        return items_management()

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
        customer, product_code = row_id.split("__", 1)

        try:
            val = float(manual_qty) if manual_qty and manual_qty.strip() else None
        except ValueError:
            return Response("Invalid quantity", status=400)

        with db.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO forecast_adjustments 
                (year, month, customer_name, product_code, manual_quantity, adjustment_reason, updated_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (year, month, customer, product_code, val, reason, "User"))
            conn.commit()
        
        return Response("Saved", status=200)

    return app


def _load_item_configs(db) -> dict[str, dict]:
    with db.get_connection() as conn:
        rows = conn.execute("SELECT * FROM item_configs").fetchall()
        return {
            row["product_code"]: {
                "is_excluded": bool(row["is_excluded"]),
                "is_budgeted": bool(row["is_budgeted"]),
                "is_visible": bool(row["is_visible"]),
                "status_label": row["status_label"]
            }
            for row in rows
        }


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
    return {row["product_code"] for row in rows}


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


def _save_exclusions(db, excluded_ids: list[str]) -> None:
    with db.get_connection() as conn:
        conn.execute("UPDATE item_configs SET is_excluded = 0")
        for pid in excluded_ids:
            conn.execute(
                "INSERT OR REPLACE INTO item_configs (product_code, is_excluded) VALUES (?, 1)",
                (pid,)
            )
        conn.commit()


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
