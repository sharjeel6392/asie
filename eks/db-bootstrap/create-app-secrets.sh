#!/bin/bash
# Creates the per-workload DB connection Secrets. Expects
# ASIE_APP_USER_PASSWORD / AIRFLOW_USER_PASSWORD / MLFLOW_USER_PASSWORD /
# RDS_HOST / RDS_PORT in the environment — normally invoked by run.sh right
# after the bootstrap Job creates those roles, not run standalone.
set -e

: "${ASIE_APP_USER_PASSWORD:?required}"
: "${AIRFLOW_USER_PASSWORD:?required}"
: "${MLFLOW_USER_PASSWORD:?required}"
: "${RDS_HOST:?required}"
: "${RDS_PORT:?required}"

kubectl -n asie-inference create secret generic asie-app-db \
  --from-literal=ASIE_DATABASE_URL="postgresql+psycopg2://asie_app_user:${ASIE_APP_USER_PASSWORD}@${RDS_HOST}:${RDS_PORT}/asie_app" \
  --dry-run=client -o yaml | kubectl apply -f -

# The DAG reads asie_app (drift metrics) in addition to Airflow's own
# metadata DB — same connection string, second namespace, since Secrets
# don't cross namespaces.
kubectl -n airflow create secret generic asie-app-db \
  --from-literal=ASIE_DATABASE_URL="postgresql+psycopg2://asie_app_user:${ASIE_APP_USER_PASSWORD}@${RDS_HOST}:${RDS_PORT}/asie_app" \
  --dry-run=client -o yaml | kubectl apply -f -

# The official Airflow chart requires exactly this key name ("connection")
# for data.metadataSecretName.
kubectl -n airflow create secret generic airflow-metadata-db \
  --from-literal=connection="postgresql+psycopg2://airflow_user:${AIRFLOW_USER_PASSWORD}@${RDS_HOST}:${RDS_PORT}/airflow_db" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl -n mlflow create secret generic mlflow-db \
  --from-literal=MLFLOW_BACKEND_STORE_URI="postgresql://mlflow_user:${MLFLOW_USER_PASSWORD}@${RDS_HOST}:${RDS_PORT}/mlflow_db" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "Created asie-app-db (ns asie-inference), airflow-metadata-db (ns airflow), mlflow-db (ns mlflow)."
