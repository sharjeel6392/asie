import sqlite3
from sqlalchemy import text

from src.db.engine import get_connection, get_engine
from src.constants import INFERENCE_DB_PATH, INFERENCE_SCHEMA_PATH
from src.logger import configure_logger


def init_db() -> bool:
    """For local SQLite: creates the table if missing — schema.sql stays
    the source of truth for local dev, no separate bootstrap step needed.
    For Postgres (RDS in-cluster): DDL is applied once by
    eks/db-bootstrap/, so this is just a connectivity check before the app
    starts serving traffic."""
    try:
        engine = get_engine()
        if engine.url.get_backend_name() == "sqlite":
            INFERENCE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(INFERENCE_DB_PATH)
            with open(INFERENCE_SCHEMA_PATH) as f:
                conn.executescript(f.read())
            conn.commit()
            conn.close()
        else:
            with get_connection() as conn:
                conn.execute(text("SELECT 1"))
        return True
    except Exception:
        configure_logger().exception("DB init/connectivity check failed")
        return False
