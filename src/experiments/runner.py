import os
import logging

logging.getLogger("alembic").setLevel(logging.CRITICAL)
logging.getLogger("alembic.runtime.migration").setLevel(logging.CRITICAL)
logging.getLogger("mlflow.store.db.utils").setLevel(logging.CRITICAL)
logging.getLogger("mlflow").setLevel(logging.WARNING)

import mlflow
from src.serving.config import Settings
from src.pipelines.pipeline import run_pipeline
from src.logger import configure_logger
from src.experiments.schemas import ExperimentResult
from typing import List

_mlflow_initialized = False
def _init_mlflow():
    global _mlflow_initialized
    if _mlflow_initialized:
        return

    mlflow.set_tracking_uri(Settings.MLFLOW_TRACKING_URI)
    mlflow.set_experiment(Settings.MLFLOW_EXPERIMENT_NAME)

    _mlflow_initialized = True
    

def run_experiments(configs: list) -> List[ExperimentResult]:
    logger = configure_logger()
    logger.info(f"CWD: {os.getcwd()}")
    logger.info(f'MLflow URI (env): {Settings.MLFLOW_TRACKING_URI}')
    _init_mlflow()
    logger.info(f'MLflow URI: {Settings.MLFLOW_TRACKING_URI}')
    logger.info(f'MLflow Experiment Name: {Settings.MLFLOW_EXPERIMENT_NAME}')
    results: List[ExperimentResult] = []
    for i, cfg in enumerate(configs):
        logger.info(f'Running experiment {i+1}/{len(configs)} with config: {cfg}')

        try:
            result = run_pipeline(cfg)
            results.append(result)

        except Exception as e:
            logger.error(f"Experiment {i+1} failed: {e}")
            results.append({
                "status": "failure",
                "error": str(e),
                "config": cfg
            })

    return results