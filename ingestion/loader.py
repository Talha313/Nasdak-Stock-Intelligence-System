# injestion/loader.py
import logging
import pandas as pd
from sqlalchemy import text
from storage.db import engine

logger = logging.getLogger(__name__)

"""
Data loading module for persisting ingested stock data into PostgreSQL.

Responsibilities:
- Store raw ingestion data (append-only audit trail)
- Store cleaned data with idempotent inserts

Design:
- raw_prices: full history, no deduplication
- prices: deduplicated, production-ready dataset
"""

def load_raw(df: pd.DataFrame) -> None:
    """
    Insert raw data into raw_prices table (append-only).

    Args:
        df (pd.DataFrame): Raw OHLCV data

    Notes:
        - No deduplication or conflict handling
        - Preserves full ingestion history for auditing/debugging
    """
    if df.empty:
        return
    try:
        sql = text("""
            INSERT INTO raw_prices (date, symbol, open, high, low, close, volume)
            VALUES (:date, :symbol, :open, :high, :low, :close, :volume)
        """)
        with engine.begin() as conn:
            conn.execute(sql, df.to_dict(orient="records"))
        logger.info(f"Raw load: {len(df)} rows appended to raw_prices")
    except Exception as e:
        logger.error(f"Failed to load raw data: {e}")
        raise


def load_prices(df: pd.DataFrame) -> dict:
    """
    Insert cleaned data into prices table.

    Args:
        df (pd.DataFrame): Cleaned OHLCV data

    Returns:
        dict: {"inserted": int, "skipped": int}

    Behavior:
        - Uses ON CONFLICT DO NOTHING for idempotency
        - Ensures safe re-runs without duplication
    """
    if df.empty:
        logger.info("Nothing to load.")
        return {"inserted": 0, "skipped": 0}

    sql = text("""
        INSERT INTO prices (date, symbol, open, high, low, close, volume)
        VALUES (:date, :symbol, :open, :high, :low, :close, :volume)
        ON CONFLICT (date, symbol) DO NOTHING
    """)

    rows     = df.to_dict(orient="records")
    inserted = 0
    skipped  = 0

    with engine.begin() as conn:
        for row in rows:
            result = conn.execute(sql, row)
            if result.rowcount == 1:
                inserted += 1
            else:
                skipped += 1

    logger.info(f"Prices load — inserted: {inserted}, skipped: {skipped}")
    return {"inserted": inserted, "skipped": skipped}