import pandas as pd
from sqlalchemy import text
from storage.db import engine


# ── Prices ──────────────────────────────────────────────
def get_price_history(symbol: str, days: int = 90) -> pd.DataFrame:
    try:
        query = text("""
            SELECT date, open, high, low, close, volume
            FROM prices
            WHERE symbol = :symbol
            ORDER BY date DESC
            LIMIT :days
        """)
        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params={"symbol": symbol, "days": days})
        return df.sort_values("date")
    except Exception:
        return pd.DataFrame()


def get_latest_prices() -> pd.DataFrame:
    """Most recent close per ticker for the overview page."""
    try:
        query = text("""
            SELECT DISTINCT ON (symbol)
                symbol, date, close, volume
            FROM prices
            ORDER BY symbol, date DESC
        """)
        with engine.connect() as conn:
            return pd.read_sql(query, conn)
    except Exception:
        return pd.DataFrame()


def get_daily_returns() -> pd.DataFrame:
    """Used for correlation heatmap."""
    try:
        query = text("""
            SELECT date, symbol, daily_return
            FROM features
            ORDER BY date
        """)
        with engine.connect() as conn:
            return pd.read_sql(query, conn)
    except Exception:
        return pd.DataFrame()


# ── Predictions ─────────────────────────────────────────
def get_predictions(days: int = 30) -> pd.DataFrame:
    try:
        query = text("""
            SELECT date, symbol, predicted_close,
                   actual_close, model_version, predicted_at
            FROM predictions
            ORDER BY date DESC, symbol
            LIMIT :limit
        """)
        with engine.connect() as conn:
            return pd.read_sql(query, conn, params={"limit": days * 10})
    except Exception:
        return pd.DataFrame()


def get_prediction_accuracy() -> pd.DataFrame:
    """Per-ticker MAE where actuals exist."""
    try:
        query = text("""
            SELECT
                symbol,
                COUNT(*)                                          AS predictions,
                ROUND(AVG(ABS(actual_close - predicted_close))::numeric, 4)  AS mae,
                ROUND(AVG(
                    ABS(actual_close - predicted_close) / actual_close * 100
                )::numeric, 2)                                    AS mape_pct
            FROM predictions
            WHERE actual_close IS NOT NULL
            GROUP BY symbol
            ORDER BY mae
        """)
        with engine.connect() as conn:
            return pd.read_sql(query, conn)
    except Exception:
        return pd.DataFrame()


# ── Model Registry ───────────────────────────────────────
def get_model_history() -> pd.DataFrame:
    try:
        query = text("""
            SELECT model_version, rmse, mae, r2,
                   is_champion, trained_at, trained_on_data_until
            FROM model_registry
            WHERE symbol = 'GLOBAL'
            ORDER BY trained_at DESC
        """)
        with engine.connect() as conn:
            return pd.read_sql(query, conn)
    except Exception:
        return pd.DataFrame()


def get_champion() -> dict | None:
    try:
        query = text("""
            SELECT model_version, rmse, mae, r2, trained_at
            FROM model_registry
            WHERE symbol = 'GLOBAL' AND is_champion = TRUE
            ORDER BY trained_at DESC LIMIT 1
        """)
        with engine.connect() as conn:
            row = conn.execute(query).fetchone()
        return dict(row._mapping) if row else None
    except Exception:
        return None


# ── Monitoring ───────────────────────────────────────────
def get_monitoring_logs(limit: int = 30) -> pd.DataFrame:
    try:
        query = text("""
            SELECT run_at, model_version, mean_error,
                   mae_7d, mae_30d, drift_detected,
                   drift_score, champion_age_days, notes
            FROM monitoring_logs
            ORDER BY run_at DESC
            LIMIT :limit
        """)
        with engine.connect() as conn:
            return pd.read_sql(query, conn, params={"limit": limit})
    except Exception:
        return pd.DataFrame()