import pytest

from src.backend.forecast_engine import ForecastTarget
from src.backend.web.form_parser import FormValidationError, parse_excluded_ids, parse_manual_quantities, parse_target_period


def test_parse_target_period_uses_default_for_missing_values():
    assert parse_target_period({}, ForecastTarget(2026, 5)) == ForecastTarget(2026, 5)


def test_parse_target_period_rejects_invalid_month():
    with pytest.raises(FormValidationError, match="月份"):
        parse_target_period({"year": "2026", "month": "13"}, ForecastTarget(2026, 5))


def test_parse_target_period_rejects_month_zero():
    with pytest.raises(FormValidationError, match="月份"):
        parse_target_period({"year": "2026", "month": "0"}, ForecastTarget(2026, 5))


def test_parse_target_period_rejects_nonnumeric():
    with pytest.raises(FormValidationError, match="年份"):
        parse_target_period({"year": "abc", "month": "5"}, ForecastTarget(2026, 5))
    with pytest.raises(FormValidationError, match="月份"):
        parse_target_period({"year": "2026", "month": ""}, ForecastTarget(2026, 5))


def test_parse_target_period_rejects_year_out_of_range():
    with pytest.raises(FormValidationError, match="年份"):
        parse_target_period({"year": "1999", "month": "5"}, ForecastTarget(2026, 5))
    with pytest.raises(FormValidationError, match="年份"):
        parse_target_period({"year": "2101", "month": "5"}, ForecastTarget(2026, 5))


def test_parse_manual_quantities_accepts_blank_and_positive_numbers():
    parsed = parse_manual_quantities(
        {
            "manual_quantity__A__P1": "",
            "manual_quantity__A__P2": "12.5",
            "other": "ignored",
        }
    )

    assert parsed == {"A__P1": None, "A__P2": 12.5}


def test_parse_manual_quantities_rejects_text_and_negative_numbers():
    with pytest.raises(FormValidationError, match="人工數量"):
        parse_manual_quantities({"manual_quantity__A__P1": "abc"})

    with pytest.raises(FormValidationError, match="人工數量"):
        parse_manual_quantities({"manual_quantity__A__P1": "-1"})

    with pytest.raises(FormValidationError, match="人工數量"):
        parse_manual_quantities({"manual_quantity__A__P1": "-1"}, type_cast=int)


def test_parse_excluded_ids_returns_checkbox_ids():
    assert parse_excluded_ids({"exclude__A__P1": "on", "manual_quantity__A__P1": "3"}) == {"A__P1"}
