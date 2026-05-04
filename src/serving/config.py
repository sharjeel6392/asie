import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Required
    MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")
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