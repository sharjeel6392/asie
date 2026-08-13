from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
import logging
import os
from airflow.exceptions import AirflowSkipException
from src.constants import DRIFT_THRESHOLD

# Matches PYTHONPATH/WORKDIR in Dockerfile.airflow. The training pipeline
# resolves its dataset relative to the working directory, so dvc pull has to
# run from the same place.
PROJECT_DIR = os.getenv("ASIE_PROJECT_DIR", "/opt/airflow/asie")

# MLFLOW_TRACKING_URI comes from the chart's env (eks/airflow-values.yaml)
# and src/ is importable via PYTHONPATH=/opt/airflow/asie (Dockerfile.airflow)
# — both used to be hardcoded here for local-only paths.

from src.pipelines.retraining_pipeline import retraining_pipeline
from src.drift.storage.drift_metrics_repository import get_latest_drift_metric


def dvc_pull(**context):
    """Fetch the training data from the S3 DVC remote.

    The dataset is deliberately not baked into the image -- the whole point of
    the DVC remote is to be the single source of truth for it, and the image
    only carries .dvc/config plus the data/*.dvc pointers. Without this task
    the pipeline dies on a missing ./data/financial_phrasebank.parquet, which
    is exactly how it failed the first time it ran in-cluster.

    Credentials come from the pod's IRSA role (airflow-irsa-sa), which has
    read access to the dvc-data/ prefix -- no keys involved.
    """
    import subprocess

    proc = subprocess.run(
        ["dvc", "pull", "--force"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
    )
    logging.info("dvc pull stdout:\n%s", proc.stdout)
    if proc.returncode != 0:
        logging.error("dvc pull stderr:\n%s", proc.stderr)
        raise RuntimeError(f"dvc pull failed with exit code {proc.returncode}")

    expected = os.path.join(PROJECT_DIR, "data", "financial_phrasebank.parquet")
    if not os.path.exists(expected):
        raise RuntimeError(
            f"dvc pull reported success but {expected} is still missing"
        )
    logging.info("Dataset present: %s (%d bytes)", expected, os.path.getsize(expected))
    return True


def check_drift(**context):
    drift_score = get_latest_drift_metric()
    if drift_score is not None:
        logging.info(f'Latest drift score: {drift_score}')

        if drift_score < DRIFT_THRESHOLD:
            raise AirflowSkipException(f'No significant drift detected (score: {drift_score}). Skipping retraining.')
        logging.info(f'Drift detected (score: {drift_score}). Continue retraining')
        return True
    else:
        raise AirflowSkipException('No drift metrics available')
    
def run_retraining(**context):
    """Run the retraining pipeline with detailed logging."""
    logging.info("=" * 80)
    logging.info("RETRAINING TASK STARTED")
    logging.info("=" * 80)
    
    try:
        should_run = context['ti'].xcom_pull(task_ids="check_drift")
        logging.info(f"Drift check result (should_run): {should_run}")

        if not should_run:
            logging.info("Skipping retraining - no drift detected")
            return
        
        logging.info("Starting pipeline with configs...")
        configs = [
            {'lr': 2e-5, 'epochs': 1, 'batch_size': 8, 'model_type': 'transformer', 'model_name': 'distilbert-base-uncased'},
            #{'lr': 3e-5, 'epochs': 3},
        ]
        logging.info(f"Config: {configs}")

        logging.info("Calling retraining_pipeline()...")
        result = retraining_pipeline(configs)
        logging.info(f'Pipeline result: {result}')

        if result['status'] not in ('success', 'skipped', 'no_selection'):
            error_msg = f'Pipeline failed: {result}'
            logging.error(error_msg)
            raise ValueError(error_msg)
        
        logging.info(f"Pipeline completed successfully with status: {result['status']}")
        logging.info("=" * 80)
    
    except Exception:
        logging.error("=" * 80)
        # logging.exception, not logging.error(str(e)) -- the latter discards
        # the traceback. When this failed in-cluster the only recorded message
        # was "maximum recursion depth exceeded", which was transformers' lazy
        # importer masking the real cause (an MLflow 403). The traceback is the
        # difference between a five-minute diagnosis and an hour of guessing.
        logging.exception("RETRAINING TASK FAILED")
        logging.error("=" * 80)
        raise

default_args = {
    "owner": "asie",
    "retries": 1,
}

with DAG(
    dag_id="asie_retraining_pipeline",
    default_args=default_args,
    start_date=datetime(2026, 4, 1),
    schedule="@daily",  
    catchup=False,
) as dag:
    dvc_task = PythonOperator(
        task_id="dvc_pull",
        python_callable=dvc_pull,
        provide_context=True,
    )

    drift_task = PythonOperator(
        task_id="check_drift",
        python_callable=check_drift,
        provide_context=True,
    )

    retrain_task = PythonOperator(
        task_id="retrain_pipeline",
        python_callable=run_retraining,
        provide_context=True,
    )

    # dvc_pull runs first so a missing dataset fails loudly on its own task,
    # rather than surfacing deep inside the training pipeline.
    dvc_task >> drift_task >> retrain_task