from pathlib import Path

# Project directories
DATA_DIR = "./data"
RAW_DATA_DIR = f"{DATA_DIR}/raw"
PREPROCESSED_DATA_DIR = f"{DATA_DIR}/preprocessed"
CONFIGS_DIR = "./configs"
LOGS_DIR = "./logs"
ARTIFACTS_DIR = "./artifacts"
MLRUNS_DIR = "./mlruns"
MODEL_REGISTRY_DIR = "./model"
EXPORTED_MODEL_DIR = "exported_model"

# Dataset artifacts
DATASET_NAME = "financial_phrasebank"
DATASET_VERSION = "v1"
RAW_DATA_FILE = f"{DATA_DIR}/external/{DATASET_NAME}.csv"
TRUE_DATA_FILE = f"{DATA_DIR}/{DATASET_NAME}.parquet"
TRAIN_DATA_FILE = "train_data.parquet"
VAL_DATA_FILE = "val_data.parquet"
DATA_MANIFEST_FILE = f"{DATA_DIR}/data_manifest.yaml"

# Training configuration and artifacts
PARAMS_FILE = f"{CONFIGS_DIR}/train.yaml"
ARTIFACTS_FILE = "run_artifacts.json"
MODEL_ARTIFACT_DIR = "./model"
MODEL_ARTIFACT_FILE = f"{MODEL_ARTIFACT_DIR}/model_artifact"
MODEL_REGISTRY_FILE = f"{MODEL_REGISTRY_DIR}/model_registry.yaml"
MODEL_DIR_NAME = "model"
TOKENIZER_FILE = "tokenizer"
TOKENIZER_DIR_NAME = "tokenizer"
EXPERIMENT_NAME = "ASIE_Experiment"
DEFAULT_MODEL_NAME = "asie-sentiment"
DEFAULT_SHADOW_MODEL_NAME = "asie-sentiment-shadow"

# Backward-compatible aliases used by existing training modules
MODEL_DIR = MODEL_ARTIFACT_DIR
MODEL_FILE = MODEL_ARTIFACT_FILE

# Model roles and serving metadata
PRIMARY_MODEL_ROLE = "primary"
SHADOW_MODEL_ROLE = "shadow"
PROMOTED_MODEL_STATE = "promoted"
MODEL_CLASS_NAME = "DistilBertForSequenceClassification"
PRIMARY_MODEL_VERSION = "v_01"
SHADOW_MODEL_VERSION = "v_02"
SERVED_MODEL_VERSION = "v0"
REQUEST_SOURCE_API = "api"
MAX_BATCH_SIZE = 32

# Exported artifact layout
PRIMARY_MODEL_PATH = f"{EXPORTED_MODEL_DIR}/{PRIMARY_MODEL_ROLE}/{MODEL_DIR_NAME}"
PRIMARY_TOKENIZER_PATH = f"{EXPORTED_MODEL_DIR}/{PRIMARY_MODEL_ROLE}/{TOKENIZER_DIR_NAME}"
SHADOW_MODEL_PATH = f"{EXPORTED_MODEL_DIR}/{SHADOW_MODEL_ROLE}/{MODEL_DIR_NAME}"
SHADOW_TOKENIZER_PATH = f"{EXPORTED_MODEL_DIR}/{SHADOW_MODEL_ROLE}/{TOKENIZER_DIR_NAME}"

# Runtime defaults
DEFAULT_MLFLOW_TRACKING_URI = "sqlite:///mlflow.db"
DEFAULT_DRIFT_STORE = "sqlite"
DEFAULT_INFERENCE_DEVICE = "cpu"
DEFAULT_LOG_LEVEL = "INFO"

# FastAPI metadata and routes
API_TITLE = "ASIE Serving API"
HEALTH_ROUTE = "/health"
PREDICT_ROUTE = "/predict"
DRIFT_ROUTE = "/drift"
METRICS_ROUTE = "/metrics"
WEBHOOK_ROUTE = "/webhook"
DRIFT_WEBHOOK_ROUTE = "/webhook/drift"

# HTTP metrics (see src/serving/metrics.py)
HTTP_REQUESTS_METRIC_NAME = "asie_http_requests_total"
HTTP_REQUESTS_METRIC_DESCRIPTION = "Total HTTP requests by method, route and status"
HTTP_LATENCY_METRIC_NAME = "asie_http_request_duration_seconds"
HTTP_LATENCY_METRIC_DESCRIPTION = "HTTP request latency in seconds"
HTTP_IN_FLIGHT_METRIC_NAME = "asie_http_requests_in_flight"
HTTP_IN_FLIGHT_METRIC_DESCRIPTION = "HTTP requests currently being served"
MODEL_LOADED_METRIC_NAME = "asie_model_loaded"
MODEL_LOADED_METRIC_DESCRIPTION = "1 if the model for this role is loaded, 0 otherwise"

# Latency buckets tuned for CPU transformer inference -- the sub-10ms buckets
# a default Histogram spends most of its resolution on are wasted here, and
# the default top bucket of 10s is too coarse to see a p95 regression.
HTTP_LATENCY_BUCKETS = (0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

# Label used when no route matched (404s). Bucketing them under one constant
# label instead of the raw path is what stops scanners and typos from
# creating unbounded time series.
UNMATCHED_ROUTE_LABEL = "unmatched"

# Inference logging
INFERENCE_DB_PATH = Path(f"{DATA_DIR}/inference.db")
INFERENCE_SCHEMA_PATH = Path("src/serving/inference_log_DB/schema.sql")

# SQLAlchemy connection string — sqlite locally by default (matches
# INFERENCE_DB_PATH), overridden by ASIE_DATABASE_URL to point at RDS
# Postgres in the cluster (see eks/db-bootstrap/).
DEFAULT_DATABASE_URL = f"sqlite:///{INFERENCE_DB_PATH.as_posix()}"

# Drift detection and metrics
DRIFT_DB_PATH = "drift.db"
DRIFT_SCHEMA_PATH = Path("src/drift/storage/schema.sql")
DRIFT_METRIC_NAME = "asie_data_drift_score"
DRIFT_METRIC_DESCRIPTION = "Aggregated drift score (feature + prediction drift)"
DRIFT_UPDATED_METRIC_NAME = "asie_drift_last_updated_timestamp_seconds"
DRIFT_UPDATED_METRIC_DESCRIPTION = (
    "Unix timestamp of the most recent drift metric row. "
    "get_latest_drift_metric() returns the newest row regardless of age, so "
    "the score gauge alone can report a stale value forever if the drift "
    "worker stops. This is what a staleness alert watches."
)
DRIFT_THRESHOLD = 0.5  # matches Prometheus DriftWarning (prometheus/alerts.yml)
DEFAULT_DRIFT_WINDOW_HOURS = 24
DEFAULT_CLI_DRIFT_WINDOW_HOURS = 1
DRIFT_MIN_SAMPLES = 10
DRIFT_RANDOM_STATE = 42
DRIFT_EVENT_TYPE = "DRIFT_DETECTED"
UNKNOWN_VALUE = "unknown"
