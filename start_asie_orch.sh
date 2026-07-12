#!/bin/bash
# 1. Activate the correct environment
source ~/asie_native/bin/activate

export AIRFLOW__SCHEDULER__SCHEDULER_ZOMBIE_TASK_THRESHOLD=600
export AIRFLOW__SCHEDULER__JOB_HEARTBEAT_SEC=5

# 2. Set Airflow paths
export AIRFLOW_HOME=/mnt/e/ASIE/airflow-home
export AIRFLOW__CORE__DAGS_FOLDER=/mnt/e/ASIE/airflow-home/dags
export PYTHONPATH=$PYTHONPATH:/mnt/e/ASIE

# 3. MLflow on Linux native storage
export MLFLOW_TRACKING_URI="sqlite:////home/kirksalvator/mlflow.db"

# 4. Memory safety for 16GB RAM
export AIRFLOW__SCHEDULER__KILLED_TASK_CLEANUP_TIME=604800
export AIRFLOW__CORE__PARALLELISM=2
export AIRFLOW__CORE__MAX_ACTIVE_TASKS_PER_DAG=1

# 5. FIX: Use fresh interpreter per task instead of fork (fixes WSL2 deadlock)
export AIRFLOW__CORE__EXECUTE_TASKS_NEW_PYTHON_INTERPRETER=True

# 6. Clean up lingering zombie processes
pkill -f airflow
sleep 2

# 7. Launch services
airflow scheduler &
airflow webserver --port 8080