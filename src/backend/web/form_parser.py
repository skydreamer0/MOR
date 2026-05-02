from __future__ import annotations

from collections.abc import Mapping

from src.backend.forecast_models import ForecastTarget


class FormValidationError(ValueError):
    pass


def parse_target_period(values: Mapping[str, object], default_target: ForecastTarget) -> ForecastTarget:
    year = _parse_int(values.get("year", default_target.year), "年份")
    month = _parse_int(values.get("month", default_target.month), "月份")

    if not 1 <= month <= 12:
        raise FormValidationError("月份必須介於 1 到 12。")
    if year < 1900:
        raise FormValidationError("年份格式不正確。")

    return ForecastTarget(year, month)


def parse_manual_quantities(form: Mapping[str, object]) -> dict[str, float | None]:
    result: dict[str, float | None] = {}
    for key, value in form.items():
        if not key.startswith("manual_quantity__"):
            continue
        row_id = key.removeprefix("manual_quantity__")
        clean = str(value).strip()
        if clean == "":
            result[row_id] = None
            continue
        try:
            quantity = float(clean)
        except ValueError as exc:
            raise FormValidationError("人工數量必須是數字。") from exc
        if quantity < 0:
            raise FormValidationError("人工數量不可小於 0。")
        result[row_id] = quantity
    return result


def parse_excluded_ids(form: Mapping[str, object]) -> set[str]:
    return {key.removeprefix("exclude__") for key in form if key.startswith("exclude__")}


def _parse_int(value: object, label: str) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise FormValidationError(f"{label}必須是整數。") from exc
