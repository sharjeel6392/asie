from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
import logging
from airflow.exceptions import AirflowSkipException
from src.constants import DRIFT_THRESHOLD

# MLFLOW_TRACKING_URI comes from the chart's env (eks/airflow-values.yaml)
# and src/ is importable via PYTHONPATH=/opt/airflow/asie (Dockerfile.airflow)
# — both used to be hardcoded here for local-only paths.

from src.pipelines.retraining_pipeline import retraining_pipeline
from src.drift.storage.drift_metrics_repository import get_latest_drift_metric


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
    
    except Exception as e:
        logging.error("=" * 80)
        logging.error(f"RETRAINING TASK FAILED: {str(e)}")
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

    drift_task >> retrain_task