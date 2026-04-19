# DB Connection (or reuse existing pattern)
# Insert drift metric
# Fetch latest drift metric

import sqlite3
from datetime import datetime
import os

DB_PATH = "drift.db"

def get_connection():
    return sqlite3.connect(DB_PATH)

def init_drift_db():
    conn = get_connection()
    cursor = conn.cursor()

    with open("src/drift/storage/schema.sql", "r") as f:
        cursor.executescript(f.read())

    conn.commit()
    conn.close()

def insert_drift_metric(final_drift_score: float):
    print(f'[DEBUG] DB PATH: {os.path.abspath(DB_PATH)}')
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
            INSERT INTO drift_metrics (timestamp, final_drift_score)
            VALUES (?, ?)
        """,
        (datetime.now().isoformat(), final_drift_score)
    )

    conn.commit()
    conn.close()

def get_latest_drift_metric() -> float:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
            SELECT final_drift_score
            FROM drift_metrics
            ORDER BY timestamp DESC
            LIMIT 1
        """
    )

    row = cursor.fetchone()
    conn.close()

    if row:
        return row[0]
    return 0.0

if __name__ =='__main__':
    init_drift_db()