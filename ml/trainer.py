# ml/trainer.py
import os
import json
import logging
import pickle
from datetime import datetime

import numpy as np
import pandas as pd
import shap
import xgboost as xgb
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sqlalchemy import text

from storage.db import engine

logger       = logging.getLogger(__name__)
MODEL_DIR    = os.getenv("MODEL_DIR", "/app/models")
FEATURE_COLS = [
    "ma_7", "ma_21", "rsi_14", "daily_return", "volatility_7",
    # one-hot encoded ticker columns added dynamically at training time
]
TICKERS = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN",
           "META", "TSLA", "INTC", "AMD", "NFLX"]


def fetch_all_features() -> pd.DataFrame:
    """Fetch full features table — all tickers, all dates."""
    query = text("""
        SELECT date, symbol, ma_7, ma_21, rsi_14,
               daily_return, volatility_7, target
        FROM features
        ORDER BY symbol, date
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    logger.info(f"Fetched {len(df)} feature rows across all tickers")
    return df


def get_champion_rmse() -> float | None:
    """Returns RMSE of current global champion, or None if none exists."""
    query = text("""
        SELECT rmse FROM model_registry
        WHERE symbol = 'GLOBAL' AND is_champion = TRUE
        ORDER BY trained_at DESC
        LIMIT 1
    """)
    with engine.connect() as conn:
        row = conn.execute(query).fetchone()
    return float(row.rmse) if row else None


def get_champion_mae() -> float | None:
    """Returns MAE of current global champion, or None if none exists."""
    query = text("""
        SELECT mae FROM model_registry
        WHERE symbol = 'GLOBAL' AND is_champion = TRUE
        ORDER BY trained_at DESC
        LIMIT 1
    """)
    with engine.connect() as conn:
        row = conn.execute(query).fetchone()
    return float(row.mae) if row else None


def get_next_version() -> str:
    from datetime import datetime
    query = text("""
        SELECT COUNT(*) as cnt FROM model_registry
        WHERE symbol = 'GLOBAL'
    """)
    with engine.connect() as conn:
        row = conn.execute(query).fetchone()
    version_num = (row.cnt or 0) + 1
    ts = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    return f"model_v{version_num}_{ts}"


def register_model(
    version: str,
    rmse: float,
    mae: float,
    r2: float,
    model_path: str,
    data_until,
    is_champion: bool
):
    with engine.begin() as conn:
        if is_champion:
            conn.execute(text("""
                UPDATE model_registry
                SET is_champion = FALSE
                WHERE symbol = 'GLOBAL' AND is_champion = TRUE
            """))

        conn.execute(text("""
            INSERT INTO model_registry
                (model_version, symbol, rmse, mae, r2,
                 is_champion, trained_on_data_until, model_path)
            VALUES
                (:version, 'GLOBAL', :rmse, :mae, :r2,
                 :is_champion, :data_until, :model_path)
            ON CONFLICT (model_version) DO NOTHING
        """), {
            "version":     version,
            "rmse":        rmse,
            "mae":         mae,
            "r2":          r2,
            "is_champion": is_champion,
            "data_until":  data_until,
            "model_path":  model_path
        })

    logger.info(
        f"Registered {version} | RMSE={rmse:.4f} | "
        f"MAE={mae:.4f} | R²={r2:.4f} | champion={is_champion}"
    )


def train() -> dict:
    """
    Full global training pipeline:
    1. Fetch all features (all tickers)
    2. One-hot encode symbol
    3. Temporal train/test split (80/20, sorted by date)
    4. Train XGBoost
    5. Evaluate RMSE, MAE, R²
    6. Compute SHAP feature importance
    7. Champion/challenger — replace champion only when RMSE and MAE rules pass
    8. Save model + metrics JSON
    """
    df = fetch_all_features()
    df = df.dropna(subset=["ma_7", "ma_21", "rsi_14",
                            "daily_return", "volatility_7", "target"])

    if len(df) < 100:
        raise ValueError(f"Not enough data to train: {len(df)} rows")

    # One-hot encode symbol so model knows which ticker it's predicting
    df = df.sort_values("date")
    dummies = pd.get_dummies(df["symbol"], prefix="ticker", dtype=int)
    df      = pd.concat([df, dummies], axis=1)

    ticker_cols  = [c for c in df.columns if c.startswith("ticker_")]
    all_features = ["ma_7", "ma_21", "rsi_14",
                    "daily_return", "volatility_7"] + ticker_cols

    X = df[all_features].astype(float)
    y = df["target"].astype(float)

    # Temporal split — no shuffle, preserves time order
    split    = int(len(X) * 0.8)
    X_train = X.iloc[:split]
    X_test  = X.iloc[split:]
    y_train, y_test = y[:split], y[split:]

    model = xgb.XGBRegressor(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        verbosity=0
    )
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False
    )

    preds = model.predict(X_test)
    rmse  = float(np.sqrt(mean_squared_error(y_test, preds)))
    mae   = float(mean_absolute_error(y_test, preds))
    r2    = float(r2_score(y_test, preds))

    logger.info(f"Evaluation — RMSE={rmse:.4f} MAE={mae:.4f} R²={r2:.4f}")

    sample_size = min(500, len(X_test))

    X_sample = X_test.iloc[:sample_size]

    explainer = shap.TreeExplainer(model)
    shap_values = explainer(X_sample)

    shap_importance = {
        f: float(v)
        for f, v in zip(all_features, np.abs(shap_values.values).mean(axis=0))
    }

    # Version + paths
    version      = get_next_version()
    trained_at_ts = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    model_filename = f"model__GLOBAL__{version}__{trained_at_ts}.pkl"
    metrics_filename = f"metrics__GLOBAL__{version}__{trained_at_ts}.json"
    model_path   = os.path.join(MODEL_DIR, f"{version}.pkl")
    metrics_path = os.path.join(MODEL_DIR, f"{version}_metrics.json")

    os.makedirs(MODEL_DIR, exist_ok=True)

    # Always save versioned copy
    payload = {
        "model":            model,
        "feature_cols":     all_features,
        "shap_importance":  shap_importance,
        "ticker_cols":      ticker_cols,
        "trained_on":       trained_at_ts,
        "metrics":          {"rmse": rmse, "mae": mae, "r2": r2}
    }
    with open(model_path, "wb") as f:
        pickle.dump(payload, f)

    # Save metrics JSON alongside model
    with open(metrics_path, "w") as f:
        json.dump({
            "version":          version,
            "rmse":             rmse,
            "mae":              mae,
            "r2":               r2,
            "shap_importance":  shap_importance,
            "trained_on":       trained_at_ts,
            "train_rows":       split,
            "test_rows":        len(X_test)
        }, f, indent=2)

    # Champion/challenger
    champion_rmse = get_champion_rmse()
    champion_mae = get_champion_mae()
    champion_mae_limit = (champion_mae * 1.05) if champion_mae is not None else None
    rmse_improved = (champion_rmse is None) or (rmse < champion_rmse)
    mae_within_tolerance = (champion_mae_limit is None) or (mae <= champion_mae_limit)
    is_champion   = rmse_improved and mae_within_tolerance

    if is_champion:
        champion_path = os.path.join(MODEL_DIR, "champion.pkl")
        with open(champion_path, "wb") as f:
            pickle.dump(payload, f)

        if champion_rmse is None:
            logger.info(
                f"First champion set: {version} "
                f"(RMSE={rmse:.4f}, MAE={mae:.4f})"
            )
        else:
            mae_msg = (
                f"{mae:.4f} <= {champion_mae_limit:.4f}"
                if champion_mae_limit is not None
                else "N/A (champion MAE missing)"
            )
            logger.info(
                f"New champion: {version} "
                f"(RMSE {rmse:.4f} < {champion_rmse:.4f}, "
                f"MAE rule: {mae_msg})"
            )
    else:
        if not rmse_improved:
            logger.info(
                f"Challenger {version} rejected: RMSE did not improve "
                f"({rmse:.4f} >= {champion_rmse:.4f})"
            )
        elif not mae_within_tolerance:
            logger.info(
                f"Challenger {version} rejected: MAE too high "
                f"({mae:.4f} > {champion_mae_limit:.4f})"
            )

    register_model(
        version=version,
        rmse=rmse,
        mae=mae,
        r2=r2,
        model_path=model_path,
        data_until=df["date"].max(),
        is_champion=is_champion
    )

    return {
        "version":          version,
        "rmse":             rmse,
        "mae":              mae,
        "r2":               r2,
        "is_champion":      is_champion,
        "shap_importance":  shap_importance,
        "model_path":       model_path,
        "metrics_path":     metrics_path
    }