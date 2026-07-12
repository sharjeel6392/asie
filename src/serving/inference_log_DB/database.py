import sqlite3
from pathlib import Path
from src.constants import INFERENCE_DB_PATH, INFERENCE_SCHEMA_PATH


def get_connection():
    INFERENCE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(INFERENCE_DB_PATH)

def init_db() -> bool:
    conn = get_connection()
    if conn == False:
        return False
    with open(INFERENCE_SCHEMA_PATH) as f:
        conn.executescript(f.read())
    
    conn.commit()
    conn.close()

    return True