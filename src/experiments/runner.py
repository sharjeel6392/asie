from src.pipelines.pipeline import run_pipeline
from src.logger import logging
from src.experiments.schemas import ExperimentResult
from typing import List

def run_experiments(configs: list) -> List[ExperimentResult]:
    """
    Execute multiple training runs with different hyperparameter configurations.

    This function orchestrates repeated pipeline executions and
    collects structured results for downstream comparison.

    Args:
        configs (list[dict]): List of configuration dictionaries
    
        Returns:
            list: List of pipeline results.
    """
    results: List[ExperimentResult] = []
    for i, cfg in enumerate(configs):
        logging.info(f'Running experiment {i+1}/{len(configs)} with config: {cfg}')
        result: ExperimentResult = run_pipeline(cfg)
        results.append(result)

    return results