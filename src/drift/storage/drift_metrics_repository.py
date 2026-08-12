import sqlite3
from datetime import datetime, timezone

from sqlalchemy import text

from src.logger import configure_logger
from src.constants import DRIFT_SCHEMA_PATH, INFERENCE_DB_PATH
from src.db.engine import get_connection, get_engine


def init_drift_db() -> bool:
    """For local SQLite: creates drift_metrics in the same local sqlite
    file inference_logs uses (mirrors the cluster topology, where both
    tables live in asie_app). For Postgres: DDL is applied once by
    eks/db-bootstrap/, so this is just a connectivity check."""
    try:
        engine = get_engine()
        if engine.url.get_backend_name() == "sqlite":
            INFERENCE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(INFERENCE_DB_PATH)
            with open(DRIFT_SCHEMA_PATH, "r") as f:
                conn.executescript(f.read())
            conn.commit()
            conn.close()
        else:
            with get_connection() as conn:
                conn.execute(text("SELECT 1"))
        return True
    except Exception:
        configure_logger().exception("Drift DB init/connectivity check failed")
        return False

def insert_drift_metric(final_drift_score: float):
    logger = configure_logger()
    with get_connection() as conn:
        conn.execute(
            text("""
                INSERT INTO drift_metrics (timestamp, final_drift_score)
                VALUES (:timestamp, :final_drift_score)
            """),
             {"timestamp": datetime.now(timezone.utc).isoformat(), "final_drift_score": final_drift_score},
        )
        conn.commit()
    logger.debug(f'Wrote drift score: {final_drift_score}')

def get_latest_drift_metric() -> float | None:
    with get_connection() as conn:
        row = conn.execute(
            text("""
                SELECT final_drift_score
                FROM drift_metrics
                ORDER BY timestamp DESC
                LIMIT 1
            """)
        ).fetchone()

    if row:
        return row[0]
    return None
