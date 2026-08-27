# ingestion/pipeline.py
import logging
from prefect import flow, task
from ingestion.fetcher import fetch_all_raw, TICKERS
from ingestion.loader import load_raw, load_prices
from storage.db import init_db

logger = logging.getLogger(__name__)

"""
Prefect ingestion pipeline.

Flow:
    1. Initialize database schema
    2. Fetch raw + cleaned data
    3. Load raw data (audit)
    4. Load cleaned data (production)

Key Properties:
    - Idempotent (safe to re-run)
    - Fault-tolerant (retries configured per task)
    - Incremental ingestion per ticker
"""

@task(name="initialise-database", retries=3, retry_delay_seconds=10)
def task_init_db():
    init_db()


@task(name="fetch-stock-data", retries=3, retry_delay_seconds=30)
def task_fetch(tickers):
    return fetch_all_raw(tickers)  # returns (raw_df, clean_df)


@task(name="load-raw-data", retries=2, retry_delay_seconds=15)
def task_load_raw(raw_df):
    load_raw(raw_df)


@task(name="load-clean-data", retries=2, retry_delay_seconds=15)
def task_load_clean(clean_df):
    return load_prices(clean_df)


@flow(name="nasdaq-ingestion-pipeline")
def ingestion_flow(tickers: list[str] = TICKERS):
    db = task_init_db()
    raw_df, clean_df = task_fetch(tickers, wait_for=[db])

    if raw_df.empty:
        logger.info("No new data to load.")
        return {"inserted": 0, "skipped": 0}

    task_load_raw(raw_df)
    summary = task_load_clean(clean_df)
    logger.info(f"Ingestion complete: {summary}")
    return summary


if __name__ == "__main__":
    ingestion_flow()