# serving/views/overview.py
import streamlit as st
import pandas as pd
from serving.components.db import get_latest_prices, get_daily_returns
from serving.components.charts import correlation_heatmap
from serving.components.theme import NASDAQ_GREEN, NASDAQ_RED


def render():
    st.title("Market Overview")
    st.caption("Live summary of all 10 tracked NASDAQ stocks")

    prices_df = get_latest_prices()

    if prices_df.empty:
        st.info("Waiting for ingestion pipeline to populate price data...")
        _render_placeholder_ticker_grid()
        return

    _render_ticker_grid(prices_df)
    st.divider()

    st.subheader("Price History")

    from serving.components.db import get_price_history
    from serving.components.charts import candlestick_chart

    col1, col2 = st.columns([1, 3])
    with col1:
        selected = st.selectbox(
            "Ticker",
            ["AAPL","MSFT","NVDA","GOOGL","AMZN",
             "META","TSLA","INTC","AMD","NFLX"]
        )
    with col2:
        days = st.selectbox(
            "Time Range",
            [30, 60, 90, 180],
            index=1,
            format_func=lambda x: f"Last {x} days"
        )

    history = get_price_history(selected, days=days)
    st.plotly_chart(
        candlestick_chart(history, selected),
        use_container_width=True
    )

    _render_correlation(get_daily_returns())


def _render_ticker_grid(df: pd.DataFrame):
    df = df.reset_index(drop=True)          
    cols = st.columns(5)
    for i, row in df.iterrows():           
        with cols[i % 5]:
            with st.container(border=True):
                st.markdown(f"**{row['symbol']}**")
                st.title(f"${row['close']:.2f}")
                vol = f"{int(row['volume']):,}"
                st.caption(f"Vol: {vol}")


def _render_placeholder_ticker_grid():
    """Shown before data is available."""
    tickers = ["AAPL","MSFT","NVDA","GOOGL","AMZN",
               "META","TSLA","INTC","AMD","NFLX"]
    cols = st.columns(5)
    for i, t in enumerate(tickers):
        with cols[i % 5]:
            st.metric(label=t, value="—", delta=None)


def _render_correlation(df: pd.DataFrame):
    st.subheader("Return Correlation Matrix")
    st.caption("Daily return correlations across all 10 tickers")
    st.plotly_chart(
        correlation_heatmap(df),
        use_container_width=True
    )