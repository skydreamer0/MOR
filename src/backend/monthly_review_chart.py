"""Presentation helpers for monthly review charts."""
from __future__ import annotations

from dataclasses import dataclass

from src.backend.monthly_review_trend import TrendSeries


@dataclass(frozen=True)
class ChartTick:
    y: float
    label: str


@dataclass(frozen=True)
class ChartLabel:
    x: float
    text: str


@dataclass(frozen=True)
class ChartMarker:
    x: float
    y: float
    title: str


@dataclass(frozen=True)
class MonthlyReviewTrendChart:
    title: str
    aria_label: str
    width: int
    height: int
    y_ticks: list[ChartTick]
    x_labels: list[ChartLabel]
    budget_points: str
    forecast_points: str
    actual_points: str
    actual_markers: list[ChartMarker]


def build_trend_chart(series: TrendSeries | None) -> MonthlyReviewTrendChart | None:
    """Return SVG-ready chart geometry for the monthly review trend section."""
    if not series or not series.points:
        return None

    chart_w = 880
    chart_h = 220
    pad_l = 56
    pad_r = 20
    pad_t = 12
    pad_b = 26
    inner_w = chart_w - pad_l - pad_r
    inner_h = chart_h - pad_t - pad_b
    step = inner_w / (len(series.points) - 1 if len(series.points) > 1 else 1)
    y_max = max(
        [p.actual for p in series.points]
        + [p.forecast for p in series.points]
        + [p.budget for p in series.points]
        + [1.0]
    )

    def x_at(index: int) -> float:
        return pad_l + index * step

    def y_at(value: float) -> float:
        return pad_t + inner_h * (1 - value / y_max)

    y_ticks = [
        ChartTick(y=y_at(y_max * frac), label=f"{y_max * frac:,.0f}")
        for frac in [0, 0.25, 0.5, 0.75, 1.0]
    ]
    x_labels = [
        ChartLabel(x=x_at(i), text=p.label)
        for i, p in enumerate(series.points)
    ]

    def polyline(values: list[float]) -> str:
        return " ".join(
            f"{x_at(i)},{y_at(value)}"
            for i, value in enumerate(values)
        )

    actual_markers = [
        ChartMarker(
            x=x_at(i),
            y=y_at(p.actual),
            title=(
                f"{p.label}\u3000實際 {p.actual:,.0f}"
                f"\u3000預估 {p.forecast:,.0f}"
                f"\u3000預算 {p.budget:,.0f}"
            ),
        )
        for i, p in enumerate(series.points)
    ]

    return MonthlyReviewTrendChart(
        title=f"近 {len(series.points)} 個月趨勢（金額）",
        aria_label="近 12 個月金額趨勢",
        width=chart_w,
        height=chart_h,
        y_ticks=y_ticks,
        x_labels=x_labels,
        budget_points=polyline([p.budget for p in series.points]),
        forecast_points=polyline([p.forecast for p in series.points]),
        actual_points=polyline([p.actual for p in series.points]),
        actual_markers=actual_markers,
    )
