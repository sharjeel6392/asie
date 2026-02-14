import sqlite3
from pathlib import Path

DB_PATH = Path('data/inference.db')

def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)

def init_db() -> bool:
    conn = get_connection()
    if conn == False:
        return False
    with open("./src/serving/inference_log_DB/schema.sql") as f:
        conn.executescript(f.read())
    
    conn.commit()
    conn.close()

    return True