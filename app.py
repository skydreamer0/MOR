from __future__ import annotations

import hashlib
from pathlib import Path

from flask import Flask, Response, render_template, request, send_file

from data_loader import default_target_from_data, load_sales_detail
from exporter import export_forecast
from forecast_config import ForecastConfig
from forecast_engine import ForecastOptions, apply_user_adjustments, build_forecast
from forecast_models import ForecastSummary
from web.form_parser import FormValidationError, parse_excluded_ids, parse_manual_quantities, parse_target_period


BASE_PATH = Path(__file__).resolve().parent


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(config or {})
    forecast_config = app.config.get("FORECAST_CONFIG", ForecastConfig())
    data_base_path = Path(app.config.get("DATA_BASE_PATH", BASE_PATH))

    @app.get("/")
    def index() -> str:
        try:
            data = load_sales_detail(data_base_path, forecast_config)
            target = default_target_from_data(data, forecast_config)
            target = parse_target_period(request.args, target)
            summary = build_forecast(
                data,
                target,
                ForecastOptions(include_all=True, max_cycle_interval_days=forecast_config.max_cycle_interval_days),
                forecast_config,
            )
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
            summary = build_forecast(
                data,
                target,
                ForecastOptions(include_all=True, max_cycle_interval_days=forecast_config.max_cycle_interval_days),
                forecast_config,
            )
            manual_quantities = parse_manual_quantities(request.form)
            excluded_ids = parse_excluded_ids(request.form)
            _validate_submitted_row_ids(summary, set(manual_quantities) | excluded_ids)
            _validate_forecast_signature(summary, request.form.get("forecast_signature", ""))
            summary = apply_user_adjustments(
                summary,
                manual_quantities=manual_quantities,
                excluded_ids=excluded_ids,
            )
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
                    f"{row.forecast_quantity:.8f}",
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
