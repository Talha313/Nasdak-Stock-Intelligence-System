#orchestration/flows.py
import logging
from prefect import flow, task
from ingestion.pipeline import ingestion_flow
from prefect.client.schemas.schedules import CronSchedule
from ml.pipeline import ml_flow
from processing.pipeline import processing_flow
from storage.db import init_db
from monitoring.monitor import run_monitoring

from monitoring.logger import setup_logging
setup_logging()
logger = logging.getLogger(__name__)


@task(name="initialise-database-orchestration", retries=3, retry_delay_seconds=10)
def task_init_db():
    init_db()

@task(name="initialise-ge-suite", retries=2, retry_delay_seconds=10)
def task_init_ge():
    """
    Ensures Great Expectations suite exists.
    Runs only if suite file is missing or empty.
    """
    import json
    import os
    from gx.create_suite import create_nasdaq_suite
    
    # suite_path = "gx/expectations/prices_suite.json"
    path = "gx/expectations/prices_suite.json"

    if os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
            if data.get("expectations"):
                return  # already initialized

    create_nasdaq_suite()


@task(name="run-monitoring", retries=1, retry_delay_seconds=10)
def task_monitor(train_result=None):
    return run_monitoring(
        model_version=train_result.get("version") if train_result else None
    )

@flow(name="nasdaq-master-pipeline")
def master_pipeline():
    """
    End-to-end pipeline:
    1. Initialize DB + GE
    2. Ingest raw + clean data
    3. Validate + engineer features
    4. Train ML + generate predictions
    """
    logger.info("Master pipeline starting")
    
    task_init_db()
    task_init_ge()

    ingestion_flow()

    processing_flow()

    ml_result = ml_flow()
    
    task_monitor(train_result=ml_result.get("training")) 
    
    logger.info("Master pipeline complete")


if __name__ == "__main__":
    master_pipeline.serve(
        name="nasdaq-daily-deployment",
        tags=["dev", "nasdaq"],
        description="Manual trigger for the full Nasdaq pipeline",
        schedules=[CronSchedule(cron="30 17 * * 1-5", timezone="America/New_York")] # runs at 5:30 PM New York time
    )
