# monitoring/logger.py
import json
import logging
import os
import sys
from datetime import datetime, timezone

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level":     record.levelname,
            "logger":    record.name,
            "module":    record.module,
            "message":   record.getMessage(),
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_record)


def setup_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    
    os.makedirs("/app/logs", exist_ok=True)

    file_handler = logging.FileHandler("/app/logs/pipeline.log")
    file_handler.setFormatter(JSONFormatter())

    # Silence noisy third-party loggers
    for noisy in [
        "yfinance",
        "urllib3",
        "sqlalchemy.engine",
        "prefect",
        "prefect.engine",
        "prefect.flow_runs",
        "httpx",
        "py.warnings",
        "great_expectations"
    ]:
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.basicConfig(
        level=logging.INFO,
        handlers=[handler, file_handler],
        force=True
    )