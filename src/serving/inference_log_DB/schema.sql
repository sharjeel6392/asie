CREATE TABLE IF NOT EXISTS inference_logs (
    request_id TEXT PRIMARY KEY,

    timestamp TEXT NOT NULL,

    -- INPUT PAYLOAD (JSON serialized)
    input_data TEXT NOT NULL,

    -- GROUND TRUTH (optional, can be NULL)
    true_label REAL,

    -- PRIMARY MODEL
    primary_model_name TEXT NOT NULL,
    primary_model_version TEXT NOT NULL,
    primary_prediction TEXT NOT NULL,
    primary_latency_ms REAL NOT NULL,

    -- SHADOW MODEL (nullable)
    shadow_model_name TEXT,
    shadow_model_version TEXT,
    shadow_predictions TEXT,
    shadow_latency_ms REAL,

    -- METADATA
    disagreement INTEGER,   -- 1 if predictions differ
    abs_diff REAL,          -- numeric difference
    request_source TEXT,    -- api, batch, test, etc.
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

    -- EMBEDDINGS
    embedding_json TEXT,    -- JSON serialized embeddings 
    input_length INTEGER
);

-- For time-based queries
CREATE INDEX IF NOT EXISTS idx_timestamp
ON inference_logs(timestamp);