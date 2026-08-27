import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from serving.components.theme import (
    NASDAQ_BLUE, NASDAQ_GREEN, NASDAQ_RED,
    NASDAQ_GRAY, NASDAQ_BG, NASDAQ_CARD, NASDAQ_BORDER
)

CHART_LAYOUT = dict(
    paper_bgcolor=NASDAQ_CARD,
    plot_bgcolor=NASDAQ_CARD,
    font=dict(color="#E8EDF5", family="Inter, sans-serif"),
    xaxis=dict(gridcolor=NASDAQ_BORDER, showgrid=True),
    yaxis=dict(gridcolor=NASDAQ_BORDER, showgrid=True),
    margin=dict(l=40, r=20, t=40, b=40),
)


def candlestick_chart(df: pd.DataFrame, symbol: str) -> go.Figure:
    """OHLC candlestick with volume bars."""
    if df.empty:
        return empty_chart(f"{symbol} — No data available")

    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=df["date"],
        open=df["open"], high=df["high"],
        low=df["low"],   close=df["close"],
        name=symbol,
        increasing_line_color=NASDAQ_GREEN,
        decreasing_line_color=NASDAQ_RED
    ))

    fig.update_layout(
        **CHART_LAYOUT,
        title=f"{symbol} Price History",
        xaxis_rangeslider_visible=False,
        height=400
    )
    return fig


def prediction_vs_actual(df: pd.DataFrame, symbol: str) -> go.Figure:
    """Line chart — predicted vs actual close."""
    if df.empty:
        return empty_chart(f"{symbol} — No predictions yet")

    sym_df = df[df["symbol"] == symbol].copy()

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=sym_df["date"], y=sym_df["actual_close"],
        name="Actual",
        line=dict(color=NASDAQ_BLUE, width=2)
    ))

    fig.add_trace(go.Scatter(
        x=sym_df["date"], y=sym_df["predicted_close"],
        name="Predicted",
        line=dict(color=NASDAQ_GREEN, width=2, dash="dash")
    ))

    fig.update_layout(
        **CHART_LAYOUT,
        title=f"{symbol} — Predicted vs Actual",
        height=350
    )
    return fig


def shap_bar_chart(shap_importance: dict) -> go.Figure:
    """Horizontal bar chart of SHAP feature importance."""
    if not shap_importance:
        return empty_chart("SHAP importance — No model data")

    items   = sorted(shap_importance.items(), key=lambda x: x[1])
    features, values = zip(*items)

    fig = go.Figure(go.Bar(
        x=list(values),
        y=list(features),
        orientation="h",
        marker_color=NASDAQ_BLUE,
        marker_line_color=NASDAQ_BORDER,
        marker_line_width=1
    ))

    fig.update_layout(
        **CHART_LAYOUT,
        title="SHAP Feature Importance",
        xaxis_title="Mean |SHAP value|",
        height=300
    )
    return fig


def mae_trend_chart(df: pd.DataFrame) -> go.Figure:
    """MAE over time from monitoring logs."""
    if df.empty:
        return empty_chart("MAE Trend — No monitoring data yet")

    fig = go.Figure()

    if "mae_7d" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["run_at"], y=df["mae_7d"],
            name="MAE 7-day",
            line=dict(color=NASDAQ_GREEN, width=2)
        ))

    if "mae_30d" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["run_at"], y=df["mae_30d"],
            name="MAE 30-day",
            line=dict(color=NASDAQ_BLUE, width=2, dash="dash")
        ))

    fig.update_layout(
        **CHART_LAYOUT,
        title="Prediction Error Trend",
        yaxis_title="MAE ($)",
        height=300
    )
    return fig


def correlation_heatmap(df: pd.DataFrame) -> go.Figure:
    """Return correlation heatmap across tickers."""
    if df.empty:
        return empty_chart("Correlation — No data")

    pivot = df.pivot_table(
        index="date", columns="symbol", values="daily_return"
    )
    corr = pivot.corr()

    fig = go.Figure(go.Heatmap(
        z=corr.values,
        x=corr.columns.tolist(),
        y=corr.index.tolist(),
        colorscale="RdBu",
        zmid=0,
        text=corr.round(2).values,
        texttemplate="%{text}",
        colorbar=dict(tickfont=dict(color="#E8EDF5"))
    ))

    fig.update_layout(
        **CHART_LAYOUT,
        title="Return Correlation Matrix",
        height=400
    )
    return fig


def empty_chart(message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper", yref="paper",
        x=0.5, y=0.5,
        showarrow=False,
        font=dict(color=NASDAQ_GRAY, size=14)
    )
    fig.update_layout(**CHART_LAYOUT, height=300)
    return fig