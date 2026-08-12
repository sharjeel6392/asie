-- Postgres port of src/serving/inference_log_DB/schema.sql. Run against
-- asie_app (owned by asie_app_user).
CREATE TABLE IF NOT EXISTS inference_logs (
    request_id TEXT PRIMARY KEY,

    timestamp TIMESTAMPTZ NOT NULL,

    -- INPUT PAYLOAD (JSON serialized)
    input_data TEXT NOT NULL,

    -- GROUND TRUTH (optional, can be NULL)
    true_label REAL,

    -- PRIMARY MODEL
    primary_model_name TEXT NOT NULL,
    primary_model_version TEXT NOT NULL,
    primary_prediction TEXT NOT NULL,
    primary_confidence REAL NOT NULL,
    primary_latency_ms REAL NOT NULL,

    -- SHADOW MODEL (nullable)
    shadow_model_name TEXT,
    shadow_model_version TEXT,
    shadow_predictions TEXT,
    shadow_confidence REAL,
    shadow_latency_ms REAL,

    -- METADATA
    disagreement INTEGER,   -- 1 if predictions differ (kept INTEGER, not
                             -- BOOLEAN, to match the app's existing 0/1 int() usage)
    abs_diff REAL,           -- numeric difference
    request_source TEXT,     -- api, batch, test, etc.
    created_at TIMESTAMPTZ DEFAULT now(),

    -- EMBEDDINGS
    embedding_json TEXT,    -- JSON serialized embeddings
    input_length INTEGER
);

-- For time-based queries. Renamed from the SQLite version's idx_timestamp
-- since Postgres index names are schema-global, not per-table.
CREATE INDEX IF NOT EXISTS idx_inference_logs_timestamp
ON inference_logs(timestamp);

GRANT ALL PRIVILEGES ON TABLE inference_logs TO asie_app_user;
