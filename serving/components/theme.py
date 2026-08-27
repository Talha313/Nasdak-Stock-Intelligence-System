# serving/components/theme.py

NASDAQ_BLUE    = "#0066CC"
NASDAQ_DARK    = "#001F5B"
NASDAQ_GREEN   = "#00C878"
NASDAQ_RED     = "#FF3B3B"
NASDAQ_GOLD    = "#F5A623"
NASDAQ_GRAY    = "#8892A4"
NASDAQ_BG      = "#0A0E1A"
NASDAQ_CARD    = "#111827"
NASDAQ_BORDER  = "#1E2D45"

PAGE_CONFIG = dict(
    page_title="NASDAQ Intelligence",
    layout="wide",
    initial_sidebar_state="expanded"
)

CSS = """
<style>

    /* Main background */
    .stApp { background-color: #0A0E1A; color: #E8EDF5; }

    [data-testid="stMetricLabel"] p {
        color: #FFFFFF !important; /* Pure white for labels */
        font-weight: 600 !important;
        font-size: 0.9rem !important;
    }
    [data-testid="stSidebarNav"] {display: none;}

    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #001F5B;
        border-right: 1px solid #1E2D45;
    }
    [data-testid="stSidebar"] .st-emotion-cache-6qob1r {
        color: #FFFFFF !important;
        font-weight: 500 !important;
    }
    .stCaption p {
        color: #FFFFFF !important;  
        font-size: 2.9rem !important;
        opacity: 0.9 !important;
    }
    
    [data-testid="stSidebar"] * { color: #E8EDF5 !important; }

    /* Metric cards */
    [data-testid="metric-container"] {
        background-color: #111827;
        border: 1px solid #1E2D45;
        border-radius: 8px;
        padding: 16px;
    }
    [data-testid="metric-container"] label { color: #8892A4 !important; }
    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        color: #E8EDF5 !important;
        font-size: 1.6rem !important;
        font-weight: 700 !important;
    }

    [data-testid="stMetricDelta"] svg { display: none; }
    .positive-delta { color: #00C878 !important; }
    .negative-delta { color: #FF3B3B !important; }

    /* DataFrames */
    [data-testid="stDataFrame"] { border: 1px solid #1E2D45; border-radius: 8px; }
    [data-testid="stDataFrame"] th {
        background-color: #1E2D45 !important;
        color: #FFFFFF !important;
    }

    /* Section headers */
    h1, h2, h3 { color: #E8EDF5 !important; font-weight: 700 !important; }
    h1 { 
        border-bottom: 2px solid #0066CC !important; 
        padding-bottom: 8px !important;
        background: transparent !important; 
    }

    /* Selectbox + inputs */
    [data-testid="stSelectbox"] > div { background-color: #111827 !important; }

    /* Tabs */
    [data-testid="stTabs"] button {
        color: #8892A4 !important;
        border-bottom: 2px solid transparent;
    }
    [data-testid="stTabs"] button[aria-selected="true"] {
        color: #0066CC !important;
        border-bottom: 2px solid #0066CC !important;
    }

    /* Hide Streamlit branding */
    #MainMenu { visibility: hidden; }
    footer    { visibility: hidden; }
    header    { visibility: hidden; }

    /* Hide the link/anchor icon on hover */
    [data-testid="stHeaderActionElements"], .st-emotion-cache-15zrgzn {
        display: none !important;
    }
    /* Specifically target the buttons that appear over headers */
    button[data-testid="stHeaderAction"] {
        display: none !important;
    }
    /* Fix the white block issue by ensuring main container transparency */
    [data-testid="stHeader"] {
        background-color: rgba(0,0,0,0) !important;
    }

    .main .block-container {
        background-color: #0A0E1A !important;
    }

    .st-expanderHeader a, .st-emotion-cache-b698h6 a {
        display: none !important;
    }
    iframe[title="streamlit_autorefresh.st_autorefresh"] {
        display: none !important;
    }
    [data-testid="stCaptionContainer"], 
    [data-testid="stCaptionContainer"] p {
        color: #FFFFFF !important; 
        font-size: 0.95rem !important;
        font-weight: 500 !important;
        line-height: 1.5 !important;
        opacity: 1 !important;
    }
        

</style>
"""


def inject_css():
    import streamlit as st
    st.markdown(CSS, unsafe_allow_html=True)


def card(content_fn):
    """Wrap content in a styled card div."""
    import streamlit as st
    st.markdown('<div style="background:#111827;border:1px solid #1E2D45;'
                'border-radius:8px;padding:20px;margin-bottom:16px;">',
                unsafe_allow_html=True)
    content_fn()
    st.markdown('</div>', unsafe_allow_html=True)