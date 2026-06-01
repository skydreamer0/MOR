"""Tests for monthly review chart presentation data."""

from src.backend.monthly_review_chart import build_trend_chart
from src.backend.monthly_review_trend import TrendPoint, TrendSeries


def test_build_trend_chart_returns_svg_ready_geometry():
    chart = build_trend_chart(TrendSeries(points=[
        TrendPoint(2026, 4, "26/04", actual=100.0, forecast=80.0, budget=120.0),
        TrendPoint(2026, 5, "26/05", actual=200.0, forecast=160.0, budget=180.0),
    ], previous_year_points=[
        TrendPoint(2025, 4, "25/04", actual=50.0, forecast=0.0, budget=0.0),
        TrendPoint(2025, 5, "25/05", actual=125.0, forecast=0.0, budget=0.0),
    ]))

    assert chart is not None
    assert chart.title == "近 2 個月趨勢（金額）"
    assert chart.width == 880
    assert chart.height == 220
    assert [label.text for label in chart.x_labels] == ["26/04", "26/05"]
    assert chart.actual_points == "56.0,103.0 860.0,12.0"
    assert chart.last_year_actual_points == "56.0,148.5 860.0,80.25"
    assert chart.last_year_actual_segments == ["56.0,148.5 860.0,80.25"]
    assert chart.actual_markers[-1].title == "26/05　實際 200　預估 160　預算 180　去年同期 125"


def test_build_trend_chart_hides_last_year_line_when_missing():
    chart = build_trend_chart(TrendSeries(points=[
        TrendPoint(2026, 5, "26/05", actual=200.0, forecast=160.0, budget=180.0),
    ], previous_year_points=[
        TrendPoint(2025, 5, "25/05", actual=0.0, forecast=0.0, budget=0.0),
    ]))

    assert chart is not None
    assert chart.last_year_actual_points == ""
    assert chart.last_year_actual_segments == []
    assert chart.aria_label == "近 12 個月金額趨勢"


def test_build_trend_chart_does_not_draw_missing_last_year_as_zero_drop():
    chart = build_trend_chart(TrendSeries(points=[
        TrendPoint(2026, 3, "26/03", actual=100.0, forecast=80.0, budget=90.0),
        TrendPoint(2026, 4, "26/04", actual=120.0, forecast=90.0, budget=100.0),
        TrendPoint(2026, 5, "26/05", actual=200.0, forecast=160.0, budget=180.0),
    ], previous_year_points=[
        TrendPoint(2025, 3, "25/03", actual=50.0, forecast=0.0, budget=0.0),
        TrendPoint(2025, 4, "25/04", actual=0.0, forecast=0.0, budget=0.0),
        TrendPoint(2025, 5, "25/05", actual=125.0, forecast=0.0, budget=0.0),
    ]))

    assert chart is not None
    assert chart.last_year_actual_points == ""
    assert chart.last_year_actual_segments == []


def test_build_trend_chart_returns_none_without_points():
    assert build_trend_chart(None) is None
    assert build_trend_chart(TrendSeries(points=[])) is None
