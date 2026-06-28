import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Required
    # Resolve absolute paths natively regardless of worker execution directory
    DEFAULT_DB_PATH = os.path.join(os.path.expanduser("~"), "mlflow.db")

    _raw_uri = os.getenv("MLFLOW_TRACKING_URI")
    if _raw_uri:
        # Enforce exactly 4 forward slashes for absolute local SQLite URIs
        if _raw_uri.startswith("sqlite:///") and not _raw_uri.startswith("sqlite:////"):
            MLFLOW_TRACKING_URI = _raw_uri.replace("sqlite:///", "sqlite:////")
        else:
            MLFLOW_TRACKING_URI = _raw_uri
    else:
        MLFLOW_TRACKING_URI = f"sqlite:////{DEFAULT_DB_PATH}"

    MODEL_RUN_ID = os.getenv("MODEL_RUN_ID")
    DRIFT_STORE = os.getenv("DRIFT_STORE", "sqlite")

    # Optional, with defaults
    MLFLOW_EXPERIMENT_NAME = os.getenv("MLFLOW_EXPERIMENT_NAME", "ASIE_Week1")
    INFERENCE_DEVICE = os.getenv("INFERENCE_DEVICE", "cpu")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    PRIMARY_MODEL_PATH = os.getenv("PRIMARY_MODEL_PATH", "exported_model/primary/model")
    PRIMARY_TOKENIZER_PATH = os.getenv("PRIMARY_TOKENIZER_PATH", "exported_model/primary/tokenizer")

    SHADOW_MODEL_PATH = os.getenv("SHADOW_MODEL_PATH", "exported_model/shadow/model")
    SHADOW_TOKENIZER_PATH = os.getenv("SHADOW_TOKENIZER_PATH", "exported_model/shadow/tokenizer")