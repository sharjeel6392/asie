import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Required
    MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")
    MODEL_RUN_ID = os.getenv("MODEL_RUN_ID")

    # Optional, with defaults
    MLFLOW_EXPERIMENT_NAME = os.getenv("MLFLOW_EXPERIMENT_NAME", "ASIE_Week1")
    INFERENCE_DEVICE = os.getenv("INFERENCE_DEVICE", "cpu")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")