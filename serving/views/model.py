# serving/views/model.py
import json
import streamlit as st
from serving.components.db import get_champion, get_model_history
from serving.components.charts import shap_bar_chart


def render():
    st.title("Model Registry")
    st.caption("Version history, performance metrics, and feature importance")

    champion = get_champion()

    # Champion banner
    if champion:
        st.success(
            f"Current Champion: {champion['model_version']} | "
            f"RMSE: {champion['rmse']:.4f} | "
            f"MAE: {champion['mae']:.4f} | "
            f"R²: {champion['r2']:.4f}"
        )
    else:
        st.warning("No champion model yet — ML pipeline hasn't run.")

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Version History")
        history_df = get_model_history()
        if history_df.empty:
            st.info("No model versions registered yet.")
        else:
            st.dataframe(
                history_df.style.format({
                    "rmse": "{:.4f}",
                    "mae":  "{:.4f}",
                    "r2":   "{:.4f}"
                }),
                use_container_width=True,
                hide_index=True
            )

    with col2:
        st.subheader("SHAP Feature Importance")
        st.caption("Mean absolute SHAP values — which features drive predictions most")

        # Load SHAP from champion pkl if available
        shap_data = _load_shap_from_champion()
        st.plotly_chart(
            shap_bar_chart(shap_data),
            use_container_width=True
        )


def _load_shap_from_champion() -> dict:
    """Load SHAP importance from champion.pkl if it exists."""
    import os
    import pickle

    path = os.getenv("MODEL_DIR", "/app/models") + "/champion.pkl"
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "rb") as f:
            payload = pickle.load(f)
        return payload.get("shap_importance", {})
    except Exception:
        return {}