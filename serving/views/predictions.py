# serving/views/predictions.py
import streamlit as st
from serving.components.db import get_predictions, get_prediction_accuracy
from serving.components.charts import prediction_vs_actual
from serving.components.theme import NASDAQ_GREEN, NASDAQ_RED
import pandas as pd

TICKERS = ["AAPL","MSFT","NVDA","GOOGL","AMZN",
           "META","TSLA","INTC","AMD","NFLX"]


def render():
    st.title("Predictions")
    st.caption("Next-day closing price predictions from the champion model")

    pred_df = get_predictions(days=60)

    col1, col2 = st.columns([1, 3])

    with col1:
        symbol = st.selectbox("Select Ticker", TICKERS)
        days = st.number_input("Filter: Last N Days", min_value=1, max_value=60, value=14)

    with col2:
        if pred_df.empty:
            st.info("No predictions yet — ML pipeline hasn't run.")
        else:
            pred_df["date"] = pd.to_datetime(pred_df["date"])
            cutoff = pd.Timestamp.today() - pd.Timedelta(days=days)
            pred_df = pred_df[pred_df["date"] >= cutoff]    
            st.plotly_chart(
                prediction_vs_actual(pred_df, symbol),
                use_container_width=True
            )

    st.divider()
    st.subheader("Accuracy by Ticker")

    acc_df = get_prediction_accuracy()
    if acc_df.empty:
        st.info("Accuracy metrics available once actuals are backfilled.")
    else:
        st.dataframe(
            acc_df.style.format({
                "mae":      "${:.4f}",
                "mape_pct": "{:.2f}%"
            }),
            use_container_width=True,
            hide_index=True
        )

    st.divider()
    st.subheader("Recent Predictions")

    if not pred_df.empty:
        display = pred_df[pred_df["symbol"] == symbol].head(20)
        st.dataframe(display, use_container_width=True, hide_index=True)