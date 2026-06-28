import os
from src.drift.storage.sqlite_store import SQLiteDriftStore

def get_drift_store() -> SQLiteDriftStore:
    backend = os.getenv('DRIFT_STORE_BACKEND', 'sqlite')

    if backend == 'sqlite':
        return SQLiteDriftStore()
    raise ValueError(f'Unsupported DRIFT_STORE_BACKENDL: {backend}')