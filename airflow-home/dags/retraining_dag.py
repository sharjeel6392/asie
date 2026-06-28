from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
import logging
import os
import sys

# Force the correct environment for all tasks in this DAG
os.environ["MLFLOW_TRACKING_URI"] = "sqlite:////home/kirksalvator/mlflow.db"


# Ensure scr/ is importable
PROJECT_ROOT = "/mnt/e/ASIE"
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.pipelines.retraining_pipeline import retraining_pipeline

# Dummy drift check (replace with real logic later)
def check_drift(**context):
    drift_score = 0.85 # simulate

    threshold = 0.7

    if drift_score > threshold:
        logging.info("Drift detected. Triggering retraining!")
        return True
    else:
        logging.info("No significant drfit.")
        return False
    
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