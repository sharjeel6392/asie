from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
from src.logger import logging
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
    should_run = context['ti'].xcom_pull(task_ids="check_drift")

    if not should_run:
        logging.info("Skipping retraining")
        return
    
    configs = [
        {'lr': 2e-5, 'epochs': 2},
        {'lr': 3e-5, 'epochs': 3},
    ]

    result = retraining_pipeline(configs)
    logging.info(f'Pipeline result: {result}')

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