# serving/views/monitoring.py
import streamlit as st
from serving.components.db import get_monitoring_logs
from serving.components.charts import mae_trend_chart
from serving.components.theme import NASDAQ_GREEN, NASDAQ_RED
import json

def render():
    st.title("Pipeline Monitoring")
    st.caption("Drift detection, prediction error trends, and pipeline health")

    logs_df = get_monitoring_logs(limit=30)

    if logs_df.empty:
        st.info("No monitoring data yet — pipeline hasn't completed a full run.")
        _render_placeholder()
        return

    latest = logs_df.iloc[0]

    # Health banner 
    drift_detected = latest.get("drift_detected", False)
    drift_feats_raw = latest.get("drift_features", "[]") 
    
    try:
        if isinstance(drift_feats_raw, str):
            feats = json.loads(drift_feats_raw)
        else:
            feats = drift_feats_raw
        feat_str = ", ".join(feats) if feats else "—"
    except Exception:
        feat_str = "Check Logs"

    if bool(drift_detected):
        st.error(
            f"Data drift detected! PSI score: "
            f"{latest.get('drift_score', 0):.4f} | "
            f"Affected features: {feat_str}"
        )
    else:
        st.success("No drift detected — model inputs are stable")

    st.divider()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("MAE (7-day)",  f"${latest.get('mae_7d',  0):.4f}" if latest.get("mae_7d")  else "—")
    col2.metric("MAE (30-day)", f"${latest.get('mae_30d', 0):.4f}" if latest.get("mae_30d") else "—")
    col3.metric("Drift Score",  f"{latest.get('drift_score', 0):.4f}")
    col4.metric("Champion Age", f"{latest.get('champion_age_days', '—')} days")

    st.divider()
    st.subheader("Error Trend")
    st.plotly_chart(mae_trend_chart(logs_df), use_container_width=True)

    st.divider()
    st.subheader("Monitoring Log")
    st.dataframe(logs_df, use_container_width=True, hide_index=True)


def _render_placeholder():
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("MAE (7-day)",  "—")
    col2.metric("MAE (30-day)", "—")
    col3.metric("Drift Score",  "—")
    col4.metric("Champion Age", "—")