# processing/transform.py
import logging
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def clean_ticker_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Applies strict validation rules to ticker data.
    Implements Tasks 1.1 through 1.8.
    Logs dropped row counts at every transformation step.
    """
    if df.empty:
        logger.warning("clean_ticker_data received an empty DataFrame — skipping.")
        return df

    # Work on a copy to ensure original (raw) data is untouched 
    clean_df = df.copy()
    initial_count = len(clean_df)
    logger.info(f"[Transform] Starting with {initial_count} rows.")

    # ------------------------------------------------------------------
    #  Null Handling & Positive Constraints
    # ------------------------------------------------------------------
    cols_to_check = ['open', 'high', 'low', 'close', 'volume']

    for col in cols_to_check:
        before = len(clean_df)

        null_count = clean_df[col].isnull().sum()
        non_positive_count = (clean_df[col] <= 0).sum()

        clean_df = clean_df[clean_df[col].notnull() & (clean_df[col] > 0)]
        dropped = before - len(clean_df)

        if dropped > 0:
            logger.warning(
                f"[1.1/1.3] Column '{col}': "
                f"{null_count} null(s), {non_positive_count} non-positive value(s) → "
                f"dropped {dropped} row(s). Remaining: {len(clean_df)}"
            )
        else:
            logger.info(f"[1.1/1.3] Column '{col}': clean — no nulls or non-positive values.")

    # ------------------------------------------------------------------
    # Volume Sanity (volume >= 100)
    # ------------------------------------------------------------------
    before = len(clean_df)
    low_volume = (clean_df['volume'] < 100).sum()
    clean_df = clean_df[clean_df['volume'] >= 100]
    dropped = before - len(clean_df)

    if dropped > 0:
        logger.warning(
            f"[1.8] Volume sanity: {low_volume} row(s) with volume < 100 → "
            f"dropped {dropped} row(s). Remaining: {len(clean_df)}"
        )
    else:
        logger.info(f"[1.8] Volume sanity: all rows have volume >= 100.")

    # ------------------------------------------------------------------
    # Price Consistency (High must be highest, Low must be lowest)
    # ------------------------------------------------------------------
    before = len(clean_df)
    valid_prices = (
        (clean_df['high'] >= clean_df['low']) &
        (clean_df['high'] >= clean_df['open']) &
        (clean_df['high'] >= clean_df['close']) &
        (clean_df['low'] <= clean_df['open']) &
        (clean_df['low'] <= clean_df['close'])
    )
    invalid_mask = ~valid_prices
    if invalid_mask.any():
        bad = clean_df[invalid_mask]
        logger.warning(
            f"[1.2] Price consistency: {invalid_mask.sum()} invalid row(s) found. Breakdown:\n"
            f"       high < low:   {(bad['high'] < bad['low']).sum()}\n"
            f"       high < open:  {(bad['high'] < bad['open']).sum()}\n"
            f"       high < close: {(bad['high'] < bad['close']).sum()}\n"
            f"       low > open:   {(bad['low'] > bad['open']).sum()}\n"
            f"       low > close:  {(bad['low'] > bad['close']).sum()}"
        )
    clean_df = clean_df[valid_prices]
    dropped = before - len(clean_df)

    if dropped > 0:
        logger.warning(f"[1.2] Price consistency: dropped {dropped} row(s). Remaining: {len(clean_df)}")
    else:
        logger.info(f"[1.2] Price consistency: all rows passed.")

    # ------------------------------------------------------------------
    # Outlier Filter (daily return > 50% is dropped)
    # ------------------------------------------------------------------
    before = len(clean_df)
    clean_df = clean_df.sort_values(['symbol', 'date'])
    clean_df['daily_return'] = clean_df.groupby('symbol')['close'].pct_change()

    outlier_mask = clean_df['daily_return'].abs() > 0.5
    outlier_count = outlier_mask.sum()

    if outlier_count > 0:
        outlier_rows = clean_df[outlier_mask][['symbol', 'date', 'close', 'daily_return']]
        logger.warning(
            f"[1.4] Outlier filter: {outlier_count} row(s) with |daily_return| > 50%:\n"
            f"{outlier_rows.to_string(index=False)}"
        )

    clean_df = clean_df[~outlier_mask]
    clean_df = clean_df.drop(columns=['daily_return'])
    dropped = before - len(clean_df)

    if dropped > 0:
        logger.warning(f"[1.4] Outlier filter: dropped {dropped} row(s). Remaining: {len(clean_df)}")
    else:
        logger.info(f"[1.4] Outlier filter: no outliers detected.")

    # ------------------------------------------------------------------
    # Deduplication — strict uniqueness on (date, symbol)
    # ------------------------------------------------------------------
    before = len(clean_df)
    duplicates = clean_df.duplicated(subset=['date', 'symbol'], keep='first')
    dup_count = duplicates.sum()

    if dup_count > 0:
        dup_rows = clean_df[duplicates][['symbol', 'date']]
        logger.warning(
            f"[1.5] Deduplication: {dup_count} duplicate (date, symbol) pair(s) found:\n"
            f"{dup_rows.to_string(index=False)}"
        )

    clean_df = clean_df.drop_duplicates(subset=['date', 'symbol'], keep='first')
    dropped = before - len(clean_df)

    if dropped > 0:
        logger.warning(f"[1.5] Deduplication: dropped {dropped} row(s). Remaining: {len(clean_df)}")
    else:
        logger.info(f"[1.5] Deduplication: no duplicates found.")

    total_dropped = initial_count - len(clean_df)
    logger.info(
        f"[Transform] Complete — {len(clean_df)}/{initial_count} rows passed "
        f"({total_dropped} dropped, {total_dropped/initial_count*100:.1f}% rejection rate)."
    )

    return clean_df