# ingestion/fetcher.py
import logging
from datetime import date, timedelta, datetime
import time
import pandas as pd
import pytz
import yfinance as yf
from sqlalchemy import text
from storage.db import engine
from processing.transform import clean_ticker_data

"""
Data ingestion module for fetching and preparing stock price data.

Responsibilities:
- Pull raw OHLCV data from Yahoo Finance (yfinance)
- Maintain incremental ingestion per ticker
- Produce:
    1. Raw dataset (audit trail → raw_prices table)
    2. Clean dataset (validated → prices table)

Design Notes:
- Raw data is never modified (append-only for traceability)
- Cleaning is minimal and deterministic
- Incremental fetch avoids re-downloading historical data
"""

logger = logging.getLogger(__name__)

TICKERS = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "INTC", "AMD", "NFLX"]
HISTORICAL_DAYS = 730


def get_latest_date_per_ticker() -> dict[str, date]:
    """
    Fetch the most recent available date per ticker from the prices table.

    Returns:
        dict[str, date]: Mapping of symbol → latest stored date

    Purpose:
        Enables incremental ingestion by determining the correct start date
        for each ticker.
    """
    query = text("""
        SELECT symbol, MAX(date) AS latest
        FROM prices
        GROUP BY symbol
    """)
    try:
        with engine.connect() as conn:
            result = conn.execute(query)
            # Ensure we handle cases where the table has no rows yet
            rows = result.fetchall()
            if not rows:
                return {}
            return {row.symbol: row.latest for row in rows}
    except Exception as e:
        logger.warning(f"Could not fetch latest dates (table might be empty): {e}")
        return {}


def fetch_ticker_raw(symbol: str, start: date, end: date) -> pd.DataFrame:
    """
    Fetch raw OHLCV data for a single ticker from Yahoo Finance.

    Args:
        symbol (str): Stock ticker (e.g., AAPL)
        start (date): Start date (inclusive)
        end (date): End date (inclusive)

    Returns:
        pd.DataFrame: Raw price data with standardized column names

    Notes:
        - No cleaning, filtering, or rounding is applied
        - Output is intended for audit storage (raw_prices)
        - Uses auto_adjust=True to account for splits/dividends
        - Authentication: yfinance uses Yahoo Finance public endpoints
        - No API key required. Rate limiting handled via 0.5s inter-request delay.
        - Pagination: yfinance handles date-range chunking internally.
    """
    logger.info(f"Fetching {symbol} from {start} to {end}")
    try:
        raw = yf.download(
            symbol,
            start=str(start),
            end=str(end + timedelta(days=1)),
            auto_adjust=True,
            progress=False
        )

        if raw.empty:
            logger.warning(f"No data returned for {symbol}")
            return pd.DataFrame()

        raw = raw.reset_index()
        raw.columns = [c[0] if isinstance(c, tuple) else c for c in raw.columns]
        raw.columns = [c.lower() for c in raw.columns]

        df = pd.DataFrame({
            "date":   pd.to_datetime(raw["date"]).dt.date,
            "symbol": symbol,
            "open":   raw["open"],
            "high":   raw["high"],
            "low":    raw["low"],
            "close":  raw["close"],
            "volume": raw["volume"],
        })

        logger.info(f"Fetched {len(df)} raw rows for {symbol}")
     
        return df
    except Exception as e:
        logger.error(f"Failed to fetch {symbol}: {e}")
        return pd.DataFrame()


def fetch_all_raw(tickers: list[str] = TICKERS) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Fetch and prepare data for multiple tickers.

    Args:
        tickers (list[str]): List of ticker symbols

    Returns:
        tuple:
            - raw_df   (pd.DataFrame): Unmodified raw data (for raw_prices)
            - clean_df (pd.DataFrame): Cleaned data (for prices)

    Behavior:
        - Determines per-ticker start date using existing DB state
        - Fetches only missing data (incremental ingestion)
        - Skips tickers already up-to-date
    """
    
    tz = pytz.timezone("America/New_York")
    today = datetime.now(tz).date()
    latest_dates = get_latest_date_per_ticker()

    raw_frames   = []
    clean_frames = []

    for symbol in tickers:
        start = (latest_dates[symbol] + timedelta(days=1)
                 if symbol in latest_dates
                 else today - timedelta(days=HISTORICAL_DAYS))

        if start > today:
            logger.info(f"{symbol} up to date, skipping.")
            continue

        raw_df = fetch_ticker_raw(symbol, start, today)
        time.sleep(0.5) 

        if raw_df.empty:
            continue

        # 1. Append to raw list 
        raw_frames.append(raw_df)
        
        # 2. Transform and append to clean list
        validated_df = clean_ticker_data(raw_df)
        clean_frames.append(validated_df)

    raw   = pd.concat(raw_frames,   ignore_index=True) if raw_frames   else pd.DataFrame()
    clean = pd.concat(clean_frames, ignore_index=True) if clean_frames else pd.DataFrame()

    logger.info(f"Total: {len(raw)} raw rows fetched | {len(clean)} rows passed validation.")
    return raw, clean