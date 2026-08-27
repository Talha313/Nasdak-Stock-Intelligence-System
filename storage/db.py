# storage/db.py
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

"""
Database connection and initialization utilities.
Handles engine creation, schema setup, and connection testing.
"""
import logging
logger = logging.getLogger(__name__)
# Connection string (Docker overrides this via .env)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://admin:password123@localhost:5432/nasdaq_db"
)

# SQLAlchemy engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,       # drops stale connections automatically
    pool_size=5,
    max_overflow=10
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

def init_db():
    """Initialize database schema from schema.sql (idempotent)."""
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    try:
        with open(schema_path, "r") as f:
            schema_sql = f.read()
        with engine.begin() as conn:
            conn.execute(text(schema_sql))
        logger.info("Database initialised.")
    except FileNotFoundError:
        logger.error(f"schema.sql not found at {schema_path}")
        raise
    except Exception as e:
        logger.error(f"Database initialisation failed: {e}")
        raise

def test_connection():
    """Verify DB connectivity using a simple SELECT 1."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Connection successful.")
    except Exception as e:
        logger.error(f"Connection failed: {e}")

if __name__ == "__main__":
    test_connection()
    init_db()