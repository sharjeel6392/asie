#!/bin/bash
# Bootstraps the RDS instance from inside the cluster (it has no public
# endpoint — this is the only path in). Creates airflow_db/mlflow_db, 3
# least-privilege roles, and applies the ported Postgres DDL to asie_app.
# Idempotent / re-runnable (survives asie.sh down + up cycles).
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
NAMESPACE="asie-inference"

cd "$REPO_ROOT/aws-provision"
RDS_HOST=$(terraform output -raw rds_endpoint)   # bare hostname, not host:port
RDS_PORT=$(terraform output -raw rds_port)
RDS_MASTER_USER=$(terraform output -raw rds_master_username)
RDS_MASTER_PASSWORD=$(terraform output -raw rds_master_password)
RDS_DB_NAME=$(terraform output -raw rds_db_name)
cd "$REPO_ROOT"

# Passwords for the 3 workload roles this run creates (or re-creates the
# secret for — the roles themselves are idempotently skipped if they
# already exist per 00_create_databases.sql, but re-running this script
# does rotate the password stored in these secrets each time; that's fine
# since nothing else has a stale copy to invalidate).
ASIE_APP_USER_PASSWORD=$(openssl rand -base64 24 | tr -d '/+=')
AIRFLOW_USER_PASSWORD=$(openssl rand -base64 24 | tr -d '/+=')
MLFLOW_USER_PASSWORD=$(openssl rand -base64 24 | tr -d '/+=')

echo "Creating asie-rds-bootstrap secret (ns $NAMESPACE)..."
kubectl -n "$NAMESPACE" create secret generic asie-rds-bootstrap \
  --from-literal=PGHOST="$RDS_HOST" \
  --from-literal=PGPORT="$RDS_PORT" \
  --from-literal=PGUSER="$RDS_MASTER_USER" \
  --from-literal=PGPASSWORD="$RDS_MASTER_PASSWORD" \
  --from-literal=PGDATABASE="$RDS_DB_NAME" \
  --from-literal=ASIE_APP_USER_PASSWORD="$ASIE_APP_USER_PASSWORD" \
  --from-literal=AIRFLOW_USER_PASSWORD="$AIRFLOW_USER_PASSWORD" \
  --from-literal=MLFLOW_USER_PASSWORD="$MLFLOW_USER_PASSWORD" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "Creating asie-db-sql configmap from db/postgres/*.sql..."
kubectl -n "$NAMESPACE" create configmap asie-db-sql \
  --from-file="$REPO_ROOT/db/postgres/" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "Running bootstrap Job..."
kubectl -n "$NAMESPACE" delete job asie-db-bootstrap --ignore-not-found
kubectl -n "$NAMESPACE" apply -f "$SCRIPT_DIR/job.yaml"
kubectl -n "$NAMESPACE" wait --for=condition=complete job/asie-db-bootstrap --timeout=300s

echo "Bootstrap complete. Creating per-workload app secrets..."
ASIE_APP_USER_PASSWORD="$ASIE_APP_USER_PASSWORD" \
AIRFLOW_USER_PASSWORD="$AIRFLOW_USER_PASSWORD" \
MLFLOW_USER_PASSWORD="$MLFLOW_USER_PASSWORD" \
RDS_HOST="$RDS_HOST" \
RDS_PORT="$RDS_PORT" \
  "$SCRIPT_DIR/create-app-secrets.sh"
