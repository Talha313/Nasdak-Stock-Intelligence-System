# serving/dashboard.py
import streamlit as st
from serving.components.theme import PAGE_CONFIG, inject_css
from serving.views import overview, predictions, model, monitoring
from streamlit_autorefresh import st_autorefresh

st.set_page_config(**PAGE_CONFIG)

inject_css()
st_autorefresh(interval=5 * 60 * 1000, key="autorefresh")

# Sidebar navigation
with st.sidebar:
    st.markdown("""
        <div style='text-align: center; padding: 10px; border-radius: 12px; background: rgba(255,255,255,0.05); margin-bottom: 20px;'>
            <h1 style='color: #00C878; font-size: 2.2rem; margin: 0; line-height: 1;'>◈</h1>
            <h2 style='color: #FFFFFF; font-size: 1.5rem; margin: 0; letter-spacing: 2px;'>NASDAQ Stock Intelligence</h2>
            <p style='color: #8892A4; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 1px;'>ML Pipeline Dashboard</p>
        </div>
    """, unsafe_allow_html=True)

    st.divider()

    page = st.radio(
        "Navigation",
        ["Market Overview", "Predictions", "Model Registry", "Monitoring"],
        label_visibility="collapsed"
    )

    st.divider()
    st.caption("Pipeline Status")

    # Quick status indicators
    from serving.components.db import get_latest_prices, get_champion
    prices = get_latest_prices()
    champ  = get_champion()

    st.markdown(
        f"{'🟢' if not prices.empty else '🔴'} Ingestion: "
        f"{'Live' if not prices.empty else 'No data'}"
    )
    st.markdown(
        f"{'🟢' if champ else '🔴'} Model: "
        f"{champ['model_version'] if champ else 'Not trained'}"
    )

# Route to page
if page == "Market Overview":
    overview.render()
elif page == "Predictions":
    predictions.render()
elif page == "Model Registry":
    model.render()
elif page == "Monitoring":
    monitoring.render()