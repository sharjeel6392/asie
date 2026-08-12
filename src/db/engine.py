import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from src.constants import DEFAULT_DATABASE_URL

_engine: Engine | None = None


def get_engine() -> Engine:
    """Lazily-initialized, process-wide SQLAlchemy engine. Defaults to the
    local SQLite file (same behavior as before this module existed);
    ASIE_DATABASE_URL overrides it to RDS Postgres in the cluster.

    pool_pre_ping is required against RDS — without it, a connection that's
    gone stale during pod idle time raises on first use instead of being
    quietly replaced. Pool sizes are kept modest since RDS is a
    db.t4g.micro (~112 max_connections) shared across 3 databases and
    several pods/pool.
    """
    global _engine
    if _engine is None:
        url = os.getenv("ASIE_DATABASE_URL", DEFAULT_DATABASE_URL)
        if url.startswith("sqlite"):
            # Preserve the old database.py behavior of creating the parent
            # dir (e.g. ./data/) on first use — sqlite3 won't create it.
            db_path = url.removeprefix("sqlite:///")
            if db_path and db_path != ":memory:":
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            # SQLite's default pool class (NullPool/SingletonThreadPool)
            # doesn't accept pool_size/max_overflow — create_engine() raises
            # TypeError if you pass them here.
            _engine = create_engine(
                url, pool_pre_ping=True, connect_args={"check_same_thread": False}
            )
        else:
            _engine = create_engine(
                url, pool_pre_ping=True, pool_size=2, max_overflow=3, pool_recycle=1800
            )
    return _engine


def get_connection():
    return get_engine().connect()
