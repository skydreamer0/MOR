"""Tests for monthly review chart presentation data."""

from src.backend.monthly_review_chart import build_trend_chart
from src.backend.monthly_review_trend import TrendPoint, TrendSeries


def test_build_trend_chart_returns_svg_ready_geometry():
    chart = build_trend_chart(TrendSeries(points=[
        TrendPoint(2026, 4, "26/04", actual=100.0, forecast=80.0, budget=120.0),
        TrendPoint(2026, 5, "26/05", actual=200.0, forecast=160.0, budget=180.0),
    ]))

    assert chart is not None
    assert chart.title == "近 2 個月趨勢（金額）"
    assert chart.width == 880
    assert chart.height == 220
    assert [label.text for label in chart.x_labels] == ["26/04", "26/05"]
    assert chart.actual_points == "56.0,103.0 860.0,12.0"
    assert chart.actual_markers[-1].title == "26/05　實際 200　預估 160　預算 180"


def test_build_trend_chart_returns_none_without_points():
    assert build_trend_chart(None) is None
    assert build_trend_chart(TrendSeries(points=[])) is None
