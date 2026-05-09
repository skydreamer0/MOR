import pandas as pd

from src.backend.data_validator import DataIssue, validate, validate_health
from src.backend.operational_views import DataHealthSummary


def test_zero_price_warning():
    df = pd.DataFrame({"單價NT(淨)": [0, 100, 0]})

    issues = validate(df, pd.DataFrame({"amount": [1000]}))

    assert DataIssue("warning", "有 2 筆單價為 0，金額估算可能不準確") in issues


def test_no_budget_warning():
    df = pd.DataFrame({"單價NT(淨)": [100]})

    issues = validate(df, None)

    assert any("預算" in issue.message for issue in issues)


def test_clean_data_no_issues():
    df = pd.DataFrame({"單價NT(淨)": [100, 200]})
    budget_df = pd.DataFrame({"amount": [1000]})

    issues = validate(df, budget_df)

    assert issues == []


def test_validate_health_does_not_warn_for_zero_budget_rows():
    health = DataHealthSummary(
        order_count=10,
        order_start=None,
        order_end=None,
        budget_month_count=1,
        budget_months=[(2026, 5)],
        missing_budget_row_count=3,
        zero_price_row_count=2,
        no_last_year_row_count=0,
    )

    issues = validate_health(health)

    assert issues == [
        DataIssue("warning", "有 2 筆單價為 0，金額估算可能不準確"),
    ]
