# processing/pipeline.py
import logging
from prefect import flow, task

from processing.features import fetch_prices as fetch_for_features
from processing.features import engineer_features, load_features
from processing.validation import run_validation
# NEW IMPORT from Task 1.0
from processing.transform import clean_ticker_data 

logger = logging.getLogger(__name__)

"""
Processing pipeline:
1. Validate prices (Great Expectations)
2. Engineer features
3. Load features
"""

@task(name="validate-prices", retries=1, retry_delay_seconds=10)
def task_validate():
    """Validates the 'prices' table using Great Expectations."""
    return run_validation() 


@task(name="engineer-features", retries=2, retry_delay_seconds=15)
def task_engineer():
    """Fetches data, applies strict Task 1.0 cleaning, and builds features."""
    # 1. Fetch data from the production 'prices' table
    df = fetch_for_features()
    
    # 2. Re-apply strict validation (Task 1.1 - 1.8) 
    # This ensures features are only built on valid data points.
    df = clean_ticker_data(df)
    
    logger.info(f"Engineering features for {len(df)} validated rows.")
    return engineer_features(df)


@task(name="load-features", retries=2, retry_delay_seconds=15)
def task_load(features_df):
    return load_features(features_df)


@flow(name="nasdaq-processing-pipeline")
def processing_flow():
    # 1. Halt pipeline if prices data fails baseline validation
    task_validate()                    
    
    # 2. Transform data and create technical indicators
    features_df = task_engineer()
    
    # 3. Load final features into the DB for ML
    summary = task_load(features_df)
    
    logger.info(f"Processing complete: {summary}")
    return summary


if __name__ == "__main__":
    processing_flow()