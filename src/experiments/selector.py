from typing import List
from src.experiments.schemas import ExperimentResult

def select_best_model(results: List[ExperimentResult]) -> ExperimentResult | None:
    """
    Select the best model from experiment results.

    Selection strategy:
        1. Filter successful runs
        2. Filter evaliation-passed models
        3. Rank by eval_f1 (descending)
        4. Return top candidate
    
    Args:
        results (list[ExperimentResult]): List of pipeline outputs
    
    Returns:
        ExperimentResult | None: Best model result or None if no valid candidates.
    """
    valid_models: List[ExperimentResult] = []

    for r in results:
        if (
            r.get("status") == "success" and
            r.get("evaluation", {}).get("passed") and
            "metrics" in r and
            "eval_f1" in r["metrics"]
        ):
            valid_models.append(r)
    
    if not valid_models:
        return None
    
    # deterministic selection
    best_model: ExperimentResult = max(
        valid_models,
        key = lambda x: x.get('metrics',{}).get('eval_f1',0)
    )

    return best_model