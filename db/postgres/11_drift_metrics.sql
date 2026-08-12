-- Postgres port of src/drift/storage/schema.sql. Run against asie_app
-- (owned by asie_app_user).
CREATE TABLE IF NOT EXISTS drift_metrics (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    final_drift_score REAL NOT NULL
);

-- The /metrics scrape path (get_latest_drift_metric) orders by timestamp
-- DESC on every call.
CREATE INDEX IF NOT EXISTS idx_drift_metrics_timestamp
ON drift_metrics(timestamp DESC);

GRANT ALL PRIVILEGES ON TABLE drift_metrics TO asie_app_user;
GRANT USAGE, SELECT ON SEQUENCE drift_metrics_id_seq TO asie_app_user;
