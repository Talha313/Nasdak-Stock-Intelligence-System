# monitoring/drift.py
import logging
import numpy as np
import pandas as pd
from sqlalchemy import text
from storage.db import engine

logger         = logging.getLogger(__name__)
FEATURE_COLS   = ["ma_7", "ma_21", "rsi_14", "daily_return", "volatility_7"]
PSI_THRESHOLD  = 0.2
N_BINS         = 10


def compute_psi(reference: np.ndarray, current: np.ndarray) -> float:
    """
    Population Stability Index.
    < 0.1  = stable
    0.1-0.2 = moderate change
    > 0.2  = significant drift
    """
    breakpoints = np.unique(
        np.percentile(reference, np.linspace(0, 100, N_BINS + 1))
    )
    ref_counts  = np.histogram(reference, bins=breakpoints)[0]
    cur_counts  = np.histogram(current,   bins=breakpoints)[0]
    ref_pct     = (ref_counts / len(reference)).clip(min=1e-6)
    cur_pct     = (cur_counts / len(current)).clip(min=1e-6)
    return float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))


def detect_data_drift() -> dict:
    """
    Compare training distribution (first 80% of features)
    vs recent 30 days. Flag features with PSI > 0.2.
    """
    query = text("""
        SELECT date, ma_7, ma_21, rsi_14, daily_return, volatility_7
        FROM features ORDER BY date
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)

    if len(df) < 50:
        logger.warning("Not enough data for drift detection")
        return {"drift_detected": False, "drift_score": 0.0,
                "drift_features": [], "details": {}}

    split     = int(len(df) * 0.8)
    reference = df.iloc[:split]
    current   = df.iloc[-30:]

    psi_scores = {}
    drifted    = []

    for col in FEATURE_COLS:
        ref_vals = reference[col].dropna().values
        cur_vals = current[col].dropna().values
        if len(ref_vals) < 10 or len(cur_vals) < 5:
            continue
        psi = compute_psi(ref_vals, cur_vals)
        psi_scores[col] = round(psi, 6)
        if psi > PSI_THRESHOLD:
            drifted.append(col)
            logger.warning(f"Drift in {col}: PSI={psi:.4f}")

    max_psi = max(psi_scores.values()) if psi_scores else 0.0

    if drifted:
        logger.warning(f"Data drift detected: {drifted}")
    else:
        logger.info(f"No drift. Max PSI={max_psi:.4f}")

    return {
        "drift_detected": len(drifted) > 0,
        "drift_score":    max_psi,
        "drift_features": drifted,
        "details":        psi_scores
    }


def compute_prediction_drift() -> dict:
    """
    Compare 7-day MAE vs 30-day MAE on closed predictions.
    Rising short-term error = model degrading.
    """
    query = text("""
        SELECT date, predicted_close, actual_close
        FROM predictions
        WHERE actual_close IS NOT NULL
        ORDER BY date DESC
        LIMIT 200
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)

    if df.empty:
        return {"mae_7d": None, "mae_30d": None, "mean_error": None}

    df["error"]     = (df["actual_close"] - df["predicted_close"]).abs()
    df["raw_error"] = df["actual_close"]  - df["predicted_close"]
    today           = df["date"].max()

    last_7  = df[df["date"] >= today - pd.Timedelta(days=7)]
    last_30 = df[df["date"] >= today - pd.Timedelta(days=30)]

    mae_7d     = float(last_7["error"].mean())   if len(last_7)  > 0 else None
    mae_30d    = float(last_30["error"].mean())  if len(last_30) > 0 else None
    mean_error = float(df["raw_error"].mean())   if len(df)      > 0 else None

    if mae_7d and mae_30d and mae_7d > mae_30d * 1.3:
        logger.warning(
            f"Prediction drift: MAE_7d={mae_7d:.4f} > "
            f"130% of MAE_30d={mae_30d:.4f}"
        )
    else:
        logger.info(f"Prediction stable. MAE_7d={mae_7d} MAE_30d={mae_30d}")

    return {
        "mae_7d":     mae_7d,
        "mae_30d":    mae_30d,
        "mean_error": mean_error
    }