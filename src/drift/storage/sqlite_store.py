import pandas as pd
from sqlalchemy import text
from src.db.engine import get_engine

class SQLiteDriftStore:
    def _query(self, start_time: str, end_time: str) -> pd.DataFrame:
        engine = get_engine()

        query = text("""
            SELECT *
            FROM inference_logs
            WHERE timestamp BETWEEN :start_time AND :end_time
            """)

        # Pass the engine (not a raw DBAPI connection) — pandas 2.x warns
        # on the latter and it also sidesteps needing to manage the
        # connection lifecycle here ourselves.
        return pd.read_sql_query(query, engine, params={"start_time": start_time, "end_time": end_time})

    def fetch_current(self, start_time: str, end_time: str) -> pd.DataFrame:
        return self._query(start_time, end_time)

    def fetch_reference(self, start_time: str, end_time: str) -> pd.DataFrame:
        return self._query(start_time, end_time)
