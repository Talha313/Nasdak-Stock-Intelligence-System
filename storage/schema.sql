-- storage/schema.sql

-- Schema design:
-- raw_prices        → append-only audit layer (no constraints)
-- prices            → cleaned, validated market data
-- features          → engineered features for ML
-- model_registry    → model versioning + metrics
-- predictions       → model outputs + backfilled actuals

-- 0. RAW (immutable audit layer)
CREATE TABLE IF NOT EXISTS raw_prices (
    id          SERIAL PRIMARY KEY,
    symbol      VARCHAR(10),
    date        DATE,
    open        NUMERIC,        -- no precision constraints
    high        NUMERIC,
    low         NUMERIC,
    close       NUMERIC,
    volume      NUMERIC,        -- NUMERIC not BIGINT, accepts anything yfinance returns
    ingested_at TIMESTAMPTZ DEFAULT NOW()
);

-- 1. CLEANED (validated market data)
CREATE TABLE IF NOT EXISTS prices (
    id          SERIAL PRIMARY KEY,
    date        DATE NOT NULL,
    symbol      VARCHAR(10) NOT NULL,
    open        NUMERIC(12, 4) CHECK (open > 0),
    high        NUMERIC(12, 4) CHECK (high > 0),
    low         NUMERIC(12, 4) CHECK (low > 0),
    close       NUMERIC(12, 4) CHECK (close > 0),
    volume      BIGINT CHECK (volume >= 0),
    ingested_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (date, symbol),
    CHECK (high >= low),              -- high can never be less than low
    CHECK (high >= open),
    CHECK (high >= close)
);

-- 2. ANALYTICS LAYER
CREATE TABLE IF NOT EXISTS features (
    id           SERIAL PRIMARY KEY,
    date         DATE NOT NULL,
    symbol       VARCHAR(10) NOT NULL,
    ma_7         NUMERIC(12, 4),
    ma_21        NUMERIC(12, 4),
    rsi_14  NUMERIC(8, 4)       CHECK (rsi_14 BETWEEN 0 AND 100),
    daily_return NUMERIC(10, 6),
    volatility_7 NUMERIC(10, 6),
    target       NUMERIC(12, 4) CHECK (target > 0),
    UNIQUE (date, symbol),
    FOREIGN KEY (date, symbol) REFERENCES prices (date, symbol)
        ON DELETE CASCADE   -- if price row is deleted, dependent feature rows are removed
);

-- 3. GOVERNANCE LAYER
CREATE TABLE IF NOT EXISTS model_registry (
    id            SERIAL PRIMARY KEY,
    model_version VARCHAR(50) NOT NULL UNIQUE,
    symbol        VARCHAR(10) NOT NULL,
    rmse          NUMERIC(10, 6) CHECK (rmse >= 0),
    mae           NUMERIC(10, 6) CHECK (mae >= 0),
    r2            NUMERIC(6, 4) CHECK (r2 BETWEEN -1 AND 1),
    is_champion   BOOLEAN DEFAULT FALSE,
    trained_at    TIMESTAMPTZ DEFAULT NOW(),
    trained_on_data_until DATE,
    model_path    TEXT
);

-- 4. SERVING LAYER
CREATE TABLE IF NOT EXISTS predictions (
    id              SERIAL PRIMARY KEY,
    date            DATE NOT NULL,
    symbol          VARCHAR(10) NOT NULL,
    predicted_close NUMERIC(12, 4) CHECK (predicted_close > 0),
    actual_close    NUMERIC(12, 4) CHECK (actual_close > 0),
    model_version   VARCHAR(50),
    predicted_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (date, symbol),
    FOREIGN KEY (model_version) REFERENCES model_registry (model_version)
        ON DELETE SET NULL   -- if model deleted, prediction stays but loses version ref
);

-- 5. MONITORING LAYER
CREATE TABLE IF NOT EXISTS monitoring_logs (
    id                SERIAL PRIMARY KEY,
    run_at            TIMESTAMPTZ DEFAULT NOW(),
    model_version     VARCHAR(50),
    mean_error        NUMERIC(10, 6),
    mae_7d            NUMERIC(10, 6),
    mae_30d           NUMERIC(10, 6),
    drift_detected    BOOLEAN DEFAULT FALSE,
    drift_features    TEXT,
    drift_score       NUMERIC(10, 6),
    champion_age_days INTEGER,
    predictions_made  INTEGER,
    notes             TEXT
);