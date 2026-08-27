# Nasdaq Stock Intelligence System
End-to-end ML pipeline for next-day Nasdaq stock price prediction. Automates ingestion, validation, feature engineering, XGBoost training, and monitoring across 10 tickers — with a champion/challenger model registry and Streamlit dashboard.
 
**Pipeline:** Yahoo Finance → PostgreSQL → Great Expectations → Feature Engineering → XGBoost → Champion/Challenger Registry → Predictions → Drift Monitoring → Dashboard
 

---
## Quickstart
 
```bash
cp .env.example .env
docker compose up --build
```
 
All 4 services start in dependency order:
 
| Service | URL | What it does |
|---|---|---|
| `db` | `localhost:5433` | PostgreSQL — 6-table schema |
| `prefect` | `http://localhost:4200` | Orchestration UI + run history |
| `pipeline` | — | Runs the full pipeline automatically |
| `dashboard` | `http://localhost:8501` | Streamlit — prices, predictions, SHAP, monitoring |
 
The pipeline triggers automatically at **5:30 PM ET on weekdays** (after market close).
 
---
## Trigger a manual run
 
1. Go to `http://localhost:4200`
2. **Deployments** → `nasdaq-daily-deployment` → **Quick Run**
3. Watch all stages go green in the flow graph

---
 
## Environment variables
 
Copy `.env.example` to `.env`. Default values work out of the box:
 
```env
POSTGRES_DB=nasdaq_db
POSTGRES_USER=admin
POSTGRES_PASSWORD=password123
DATABASE_URL=postgresql://admin:password123@db:5432/nasdaq_db
```

---
## Project Structure

```text
nasdaq-intelligence/
├── ingestion/               # Data extraction + loading
├── processing/              # Validation + feature engineering
├── ml/                      # XGBoost trainer + prediction pipeline
├── monitoring/              # Drift + monitoring
├── serving/                 # Streamlit dashboard
│   ├── dashboard.py
│   ├── views/
│   └── components/
├── storage/                 # DB config + schema
├── orchestration/           # Prefect master flow + cron schedule
├── gx/                      # Great Expectations config + expectations suite
├── models/                  # Saved model artifacts (champion.pkl, metrics JSON)
├── logs/                    # Pipeline run logs (JSON structured)
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

---
## Storage design
 
Six PostgreSQL tables with explicit constraints and FK relationships:
 
| Table | Purpose |
|---|---|
| `raw_prices` | Append-only audit log — immutable, no constraints |
| `prices` | Validated production data — CHECK constraints, UNIQUE(date, symbol) |
| `features` | Engineered ML inputs — MA-7/21, RSI-14, volatility, target |
| `model_registry` | Version history — champion/challenger tracking, RMSE/MAE/R² |
| `predictions` | Model outputs — predicted + backfilled actual close |
| `monitoring_logs` | Per-run drift scores, rolling MAE, pipeline health |
 
**Why PostgreSQL:** Relational structure fits FK dependencies (prices → features → predictions). CHECK constraints enforce domain rules (close > 0, RSI BETWEEN 0 AND 100) at the DB level. Transactional atomicity is required for champion promotion — demoting old champion and inserting new one must be a single operation.
 
---

## Transformation logic
 
Eight deterministic cleaning rules run on every ingestion batch. All inserts use `ON CONFLICT DO NOTHING` — idempotent by design.
 
| Rule | Logic | Assumption |
|---|---|---|
| Null removal | Drop rows with null in any OHLCV column | Sparse data safer to drop than impute for financial prediction |
| Positive prices | Drop if close/open/high/low ≤ 0 | Negative prices are data corruption |
| Volume sanity | Drop if volume < 100 | Filters pre-market zero-volume artefacts |
| OHLC consistency | Drop if high < low, open, or close | Structurally invalid — Yahoo Finance occasionally returns malformed rows |
| Outlier filter | Drop if \|daily return\| > 50% | Single-day moves this large are data errors; splits handled by auto_adjust |
| Deduplication | Keep first on (date, symbol) | Safe re-run guarantee |
| RSI warm-up | Drop first ~14 rows per ticker | RSI undefined until EWM has enough history |
| Target column | next-day close via shift(-1), last row dropped | Predicting next calendar day; last row has no future value |
 
---
 
## Monitoring & debugging
 
**If a pipeline run fails:**
1. Open `http://localhost:4200` → click the failed run → find the red task → read the log
2. Check container logs: `docker compose logs pipeline`
3. Query monitoring table: `docker exec -it nasdaq-db psql -U admin -d nasdaq_db -c "SELECT drift_detected, drift_score, notes FROM monitoring_logs ORDER BY run_at DESC LIMIT 1;"`
4. If GE validation failed: open `gx/uncommitted/data_docs/local_site/index.html` — shows exactly which expectation failed
**Drift interpretation:**
 
| PSI score | Meaning |
|---|---|
| < 0.1 | Stable — no action needed |
| 0.1 – 0.2 | Monitor — watch next few runs |
| > 0.2 | Significant drift — consider retraining on recent data |
 
**JSON logs** at `/app/logs/pipeline.log` — filter with `jq`:
```bash
docker exec -it nasdaq-pipeline jq 'select(.level=="ERROR")' /app/logs/pipeline.log
```
 
---
 
## Useful commands
 
```bash
# Stop everything (keeps DB data)
docker compose down
 
# Full reset — DELETES all data
docker compose down -v
 
# Open database shell
docker exec -it nasdaq-db psql -U admin -d nasdaq_db
 
# Run backfill (seeds historical predictions for dashboard)
docker exec -it nasdaq-pipeline python scripts/backfill_predictions.py
 
# View live logs
docker compose logs -f pipeline
 
# Rebuild after code changes
docker compose up --build
```
---