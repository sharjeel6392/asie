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

def get_latest_drift_record() -> tuple[float, datetime] | None:
    """Newest drift row as (score, timestamp), or None if the table is empty.

    The timestamp matters because this query returns the newest row no matter
    how old it is -- if the drift worker stops, the score alone looks
    perfectly healthy forever. Callers that export the score should export
    its age alongside it so staleness is alertable.
    """
    with get_connection() as conn:
        row = conn.execute(
            text("""
                SELECT final_drift_score, timestamp
                FROM drift_metrics
                ORDER BY timestamp DESC
                LIMIT 1
            """)
        ).fetchone()

    if not row:
        return None

    score, ts = row[0], row[1]

    # SQLite hands back the ISO string it was given; Postgres TIMESTAMPTZ
    # comes back as a datetime. Normalise to an aware datetime either way.
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    return score, ts


def get_latest_drift_metric() -> float | None:
    record = get_latest_drift_record()
    return record[0] if record else None
