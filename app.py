from __future__ import annotations

from pathlib import Path

from flask import Flask, Response, render_template, request, send_file

from data_loader import default_target_from_data, load_sales_detail
from exporter import export_forecast
from forecast_config import ForecastConfig
from forecast_engine import ForecastOptions, apply_user_adjustments, build_forecast
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
        return render_template(
            "index.html",
            year=summary.year if summary else request.args.get("year", ""),
            month=summary.month if summary else request.args.get("month", ""),
            rows=visible_rows,
            total=summary.total if summary else 0,
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
            summary = apply_user_adjustments(
                summary,
                manual_quantities=parse_manual_quantities(request.form),
                excluded_ids=parse_excluded_ids(request.form),
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


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
