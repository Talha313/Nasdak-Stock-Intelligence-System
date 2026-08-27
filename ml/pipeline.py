# ml/pipeline.py
import logging
from prefect import flow, task
from ml.trainer import train
from ml.predictor import generate_predictions

logger = logging.getLogger(__name__)


@task(name="train-global-model", retries=1, retry_delay_seconds=30)
def task_train():
    result = train()
    logger.info(
        f"Training done — {result['version']} | "
        f"RMSE={result['rmse']:.4f} | champion={result['is_champion']}"
    )
    return result


@task(name="generate-predictions", retries=2, retry_delay_seconds=15)
def task_predict():
    results = generate_predictions()
    logger.info(f"Generated {len(results)} predictions")
    return results


@flow(name="nasdaq-ml-pipeline")
def ml_flow():
    train_result    = task_train()
    # wait_for ensures predict only runs after train completes
    predict_results = task_predict(wait_for=[train_result])
    return {
        "training":    train_result,
        "predictions": predict_results
    }


if __name__ == "__main__":
    ml_flow()