# ml/predictor.py
import os
import pickle
import logging
from datetime import date, timedelta

import pandas as pd
from sqlalchemy import text

from storage.db import engine

logger    = logging.getLogger(__name__)
MODEL_DIR = os.getenv("MODEL_DIR", "/app/models")
TICKERS   = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN",
             "META", "TSLA", "INTC", "AMD", "NFLX"]


def load_champion() -> dict | None:
    path = os.path.join(MODEL_DIR, "champion.pkl")
    if not os.path.exists(path):
        logger.warning("No champion model found at /app/models/champion.pkl")
        return None
    with open(path, "rb") as f:
        return pickle.load(f)


def get_champion_version() -> str | None:
    query = text("""
        SELECT model_version FROM model_registry
        WHERE symbol = 'GLOBAL' AND is_champion = TRUE
        ORDER BY trained_at DESC LIMIT 1
    """)
    with engine.connect() as conn:
        row = conn.execute(query).fetchone()
    return row.model_version if row else None


def fetch_latest_features_all() -> pd.DataFrame:
    """Most recent feature row per ticker."""
    query = text("""
        SELECT DISTINCT ON (symbol)
            symbol, ma_7, ma_21, rsi_14, daily_return, volatility_7
        FROM features
        ORDER BY symbol, date DESC
    """)
    with engine.connect() as conn:
        return pd.read_sql(query, conn)


def next_trading_day() -> date:
    d = date.today() + timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def backfill_actuals():
    with engine.begin() as conn:
        result = conn.execute(text("""
            UPDATE predictions p
            SET actual_close = pr.close
            FROM prices pr
            WHERE p.symbol        = pr.symbol
              AND p.date           = pr.date
              AND p.actual_close   IS NULL
        """))
    logger.info(f"Backfilled {result.rowcount} actual_close values")


def generate_predictions() -> list[dict]:
    champion = load_champion()
    if champion is None:
        logger.error("No champion model — skipping predictions")
        return []

    features_df  = fetch_latest_features_all()
    pred_date    = next_trading_day()
    version      = get_champion_version()
    ticker_cols  = champion["ticker_cols"]

    # Reconstruct one-hot encoding for current tickers
    dummies     = pd.get_dummies(features_df["symbol"], prefix="ticker")
    features_df = pd.concat([features_df, dummies], axis=1)

    # Ensure all ticker columns from training exist (fill missing with 0)
    for col in ticker_cols:
        if col not in features_df.columns:
            features_df[col] = 0

    insert_sql = text("""
        INSERT INTO predictions
            (date, symbol, predicted_close, model_version)
        VALUES
            (:date, :symbol, :predicted_close, :model_version)
        ON CONFLICT (date, symbol) DO NOTHING
    """)

    results = []

    for _, row in features_df.iterrows():
        try:
            symbol = row["symbol"]
            X      = row[champion["feature_cols"]].values.reshape(1, -1)
            pred   = float(champion["model"].predict(X)[0])

            with engine.begin() as conn:
                conn.execute(insert_sql, {
                    "date":            pred_date,
                    "symbol":          symbol,
                    "predicted_close": round(pred, 4),
                    "model_version":   version
                })

            logger.info(f"{symbol} → ${pred:.2f} for {pred_date}")
            results.append({
                "symbol":          symbol,
                "date":            pred_date,
                "predicted_close": pred
            })

        except Exception as e:
            logger.error(f"Prediction failed for {row.get('symbol')}: {e}")

    backfill_actuals()
    return results