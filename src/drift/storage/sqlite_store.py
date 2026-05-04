import sqlite3
import pandas as pd
from src.serving.inference_log_DB.database import DB_PATH

class SQLiteDriftStore:
    def _query(self, start_time: str, end_time: str) -> pd.DataFrame:
        conn = sqlite3.connect(DB_PATH)

        query = """
            SELECT *
            FROM inference_logs
            WHERE timestamp BETWEEN ? AND ?
            """
        
        df = pd.read_sql_query(query, conn, params=(start_time, end_time))
        conn.close()

        return df
    
    def fetch_current(self, start_time: str, end_time: str) -> pd.DataFrame:
        return self._query(start_time, end_time)
    
    def fetch_reference(self, start_time: str, end_time: str) -> pd.DataFrame:
        return self._query(start_time, end_time)
