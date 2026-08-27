"""
One-time backfill script.
Generates historical predictions using the champion model
on all existing feature rows and inserts them with actuals already filled.
Run once before the presentation.

Usage:
    docker exec -it nasdaq-pipeline python scripts/backfill_predictions.py
"""
import os
import pickle
import pandas as pd
from sqlalchemy import text
from storage.db import engine

MODEL_DIR = os.getenv("MODEL_DIR", "/app/models")


def backfill():
    # 1. Get actual champion version from DB
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT model_version FROM model_registry
            WHERE is_champion = TRUE AND symbol = 'GLOBAL'
            ORDER BY trained_at DESC LIMIT 1
        """)).fetchone()

    if not row:
        print("ERROR: No champion model found in model_registry. Run the pipeline first.")
        return

    champion_version = row.model_version
    print(f"Champion version: {champion_version}")

    # 2. Load champion model
    path = os.path.join(MODEL_DIR, "champion.pkl")
    if not os.path.exists(path):
        print(f"ERROR: {path} not found. Run the pipeline first.")
        return

    print("Loading champion model...")
    with open(path, "rb") as f:
        payload = pickle.load(f)

    model        = payload["model"]
    feature_cols = payload["feature_cols"]
    ticker_cols  = payload["ticker_cols"]

    # 3. Fetch all feature rows with targets
    print("Fetching all feature rows...")
    with engine.connect() as conn:
        df = pd.read_sql(text("""
            SELECT f.date, f.symbol, f.target AS actual_close,
                   f.ma_7, f.ma_21, f.rsi_14, f.daily_return, f.volatility_7
            FROM features f
            WHERE f.target IS NOT NULL
            ORDER BY f.symbol, f.date
        """), conn)

    print(f"Got {len(df)} feature rows across all tickers.")

    # 4. One-hot encode symbol — must match training
    dummies = pd.get_dummies(df["symbol"], prefix="ticker", dtype=int)
    df = pd.concat([df, dummies], axis=1)

    for col in ticker_cols:
        if col not in df.columns:
            df[col] = 0

    # 5. Generate predictions
    X = df[feature_cols].astype(float)
    df["predicted_close"] = model.predict(X).round(4)

    # 6. Insert into predictions table
    sql = text("""
        INSERT INTO predictions
            (date, symbol, predicted_close, actual_close, model_version)
        VALUES
            (:date, :symbol, :predicted_close, :actual_close, :model_version)
        ON CONFLICT (date, symbol) DO NOTHING
    """)

    inserted = 0
    with engine.begin() as conn:
        for _, row in df.iterrows():
            result = conn.execute(sql, {
                "date":            row["date"],
                "symbol":          row["symbol"],
                "predicted_close": float(row["predicted_close"]),
                "actual_close":    float(row["actual_close"]),
                "model_version":   champion_version
            })
            inserted += result.rowcount

    print(f"Done. Inserted {inserted} historical predictions with actuals.")


if __name__ == "__main__":
    backfill()