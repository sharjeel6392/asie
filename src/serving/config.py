import os
from pathlib import Path
from dotenv import load_dotenv

from src.constants import (
    DEFAULT_DRIFT_STORE,
    DEFAULT_INFERENCE_DEVICE,
    DEFAULT_LOG_LEVEL,
    DEFAULT_MLFLOW_TRACKING_URI,
    EXPERIMENT_NAME,
    PRIMARY_MODEL_PATH,
    PRIMARY_TOKENIZER_PATH,
    SHADOW_MODEL_PATH,
    SHADOW_TOKENIZER_PATH,
)

load_dotenv()

class Settings:
    # Required
    # Resolve absolute paths natively regardless of worker execution directory
    DEFAULT_DB_PATH = os.path.join(os.path.expanduser("~"), "mlflow.db")

    _raw_uri = os.getenv("MLFLOW_TRACKING_URI", DEFAULT_MLFLOW_TRACKING_URI)
    if _raw_uri:
        # Enforce exactly 4 forward slashes for absolute local SQLite URIs
        if _raw_uri.startswith("sqlite:///") and not _raw_uri.startswith("sqlite:////"):
            MLFLOW_TRACKING_URI = _raw_uri.replace("sqlite:///", "sqlite:////")
        else:
            MLFLOW_TRACKING_URI = _raw_uri
    else:
        MLFLOW_TRACKING_URI = f"sqlite:////{DEFAULT_DB_PATH}"

    MODEL_RUN_ID = os.getenv("MODEL_RUN_ID")
    DRIFT_STORE = os.getenv("DRIFT_STORE", DEFAULT_DRIFT_STORE)

    # Optional, with defaults
    MLFLOW_EXPERIMENT_NAME = os.getenv("MLFLOW_EXPERIMENT_NAME", EXPERIMENT_NAME)
    INFERENCE_DEVICE = os.getenv("INFERENCE_DEVICE", DEFAULT_INFERENCE_DEVICE)
    LOG_LEVEL = os.getenv("LOG_LEVEL", DEFAULT_LOG_LEVEL)

    PRIMARY_MODEL_PATH = os.getenv("PRIMARY_MODEL_PATH", PRIMARY_MODEL_PATH)
    PRIMARY_TOKENIZER_PATH = os.getenv("PRIMARY_TOKENIZER_PATH", PRIMARY_TOKENIZER_PATH)

    SHADOW_MODEL_PATH = os.getenv("SHADOW_MODEL_PATH", SHADOW_MODEL_PATH)
    SHADOW_TOKENIZER_PATH = os.getenv("SHADOW_TOKENIZER_PATH", SHADOW_TOKENIZER_PATH)