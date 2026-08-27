# monitoring/monitor.py
import json
import logging
from datetime import date
from sqlalchemy import text
from storage.db import engine
from monitoring.drift import detect_data_drift, compute_prediction_drift

logger = logging.getLogger(__name__)

def run_monitoring(model_version: str = None) -> dict:
    """
    Runs after each pipeline execution:
    1. Data drift detection (PSI per feature)
    2. Prediction drift (rolling MAE)
    3. Writes result to monitoring_logs table
    """
    logger.info("Starting monitoring run")

    drift_report = detect_data_drift()
    pred_drift   = compute_prediction_drift()

    # Get champion version if not passed in
    if not model_version:
        query = text("""
            SELECT model_version FROM model_registry
            WHERE symbol = 'GLOBAL' AND is_champion = TRUE
            ORDER BY trained_at DESC LIMIT 1
        """)
        with engine.connect() as conn:
            row = conn.execute(query).fetchone()
        model_version = row.model_version if row else None

    # Champion age
    age_days = None
    if model_version:
        query = text("""
            SELECT trained_at FROM model_registry
            WHERE model_version = :v
        """)
        with engine.connect() as conn:
            row = conn.execute(query, {"v": model_version}).fetchone()
        if row:
            age_days = (date.today() - row.trained_at.date()).days

    # Predictions made today
    with engine.connect() as conn:
        count = conn.execute(text("""
            SELECT COUNT(*) FROM predictions
            WHERE predicted_at::date = CURRENT_DATE
        """)).scalar()

    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO monitoring_logs (
                model_version, mean_error, mae_7d, mae_30d,
                drift_detected, drift_features, drift_score,
                champion_age_days, predictions_made, notes
            ) VALUES (
                :version, :mean_error, :mae_7d, :mae_30d,
                :drift_detected, :drift_features, :drift_score,
                :age_days, :predictions_made, :notes
            )
        """), {
            "version":          model_version,
            "mean_error":       pred_drift.get("mean_error"),
            "mae_7d":           pred_drift.get("mae_7d"),
            "mae_30d":          pred_drift.get("mae_30d"),
            "drift_detected":   drift_report["drift_detected"],
            "drift_features":   json.dumps(drift_report["drift_features"]),
            "drift_score":      drift_report["drift_score"],
            "age_days":         age_days,
            "predictions_made": count,
            "notes": (
                f"Drift in: {drift_report['drift_features']}"
                if drift_report["drift_detected"]
                else "All checks passed"
            )
        })

    logger.info(
        f"Monitoring complete — "
        f"drift={drift_report['drift_detected']}, "
        f"mae_7d={pred_drift.get('mae_7d')}, "
        f"predictions={count}"
    )

    return {
        "drift":      drift_report,
        "prediction": pred_drift,
        "predictions_made": count
    }
if __name__ == "__main__":
    result = run_monitoring()
    print(result)