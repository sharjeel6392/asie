import traceback

from src.experiments.runner import run_experiments
from src.experiments.selector import select_best_model
from src.models.model_registry import register_shadow_model
from src.models.export_model import export_models
from src.logger import configure_logger

def _deploy_as_shadow(best_model: dict, logger) -> str | None:
    """Commit the new candidate as the deployed shadow version.

    Failure here is logged, not raised. The training half of the run has
    already succeeded -- the model exists, is registered, and its weights are
    in S3 -- and losing all of that because a deploy key was missing would mean
    re-running an hour of training to fix a one-line credential problem. The
    version can be committed by hand or by the next run.
    """
    from src.gitops.values_writer import update_deployed_version

    run_id = best_model.get("run_id")
    f1 = (best_model.get("metrics") or {}).get("eval_f1")

    try:
        return update_deployed_version(
            key="shadowVersion",
            version=run_id,
            message=(
                f"deploy: shadow -> {run_id}\n\n"
                f"Retrained candidate, offline eval_f1 {f1}.\n\n"
                "Deployed as SHADOW, not primary: it runs against live traffic\n"
                "with its output logged and never returned, which is how the\n"
                "promotion gate gathers the online evidence it needs. Promotion\n"
                "is a later, separate decision."
            ),
        )
    except Exception:
        logger.exception(
            "Shadow deploy commit failed. The model is registered and exported; "
            "only the git commit is missing, so it can be deployed by hand."
        )
        return None


def retraining_pipeline(configs: list[dict]) -> dict:
    """
    Orchestrates full retraining flow:
    experiment → selection → registry → export

    Returns:
        dict: summary of pipeline execution
    """
    logger = configure_logger()
    try:
        logger.info('Starting retraining pipeline...')

        # Step 1: Run experiments
        results = run_experiments(configs)
        if not results:
            logger.warning("No experiment results found.")
            return {"status": "no_result"}
        
        # Step 2: Select best model
        best_model = select_best_model(results)

        if not best_model:
            logger.warning("No valid model selected.")
            return {"status": "no_selection"}
        
        # Step 3: Register shadow (with internal gating)
        updated = register_shadow_model(best_model)

        if not updated:
            logger.info("Registry not updated (model rejected).")
            return {
                "status": "skipped",
                "reason": "model_not_better"
            }
            
        # Step 4: Export (only if state changed)
        export_models()

        # Step 5: Deploy the new candidate AS SHADOW.
        #
        # This is what closes the loop. Until now the pipeline ended here, with
        # fresh weights in S3 that no running pod would ever load -- the gap
        # recorded in DEPLOYMENT_ARCHITECTURE.md §1. Committing the run_id to
        # gitops/values/inference.yaml is the deploy; ArgoCD does the rest.
        #
        # Shadow, not primary, and deliberately so: the promotion gate needs
        # online evidence before this model serves anyone, and it can only
        # gather that evidence by running in shadow first. Promotion is a
        # separate decision made later by evaluate_promotion(), against the
        # traffic this deployment produces.
        deployed = _deploy_as_shadow(best_model, logger)

        logger.info("Retraining pipeline completed successfully.")

        return {
            "status": "success",
            "run_id": best_model.get('run_id'),
            "metrics": best_model.get('metrics'),
            "shadow_deploy_commit": deployed,
        }
    
    except Exception as e:
        logger.error(f'Retrainng pipeline failed: {e}')
        logger.error(f'Traceback:\n{traceback.format_exc()}')
        return {
            'status': "failure",
            "error": str(e)
        }
    
# if __name__ == '__main__':
#     config_from_file = {
#     "model_name": "distilbert-base-uncased",
#     "epochs": 3,
#     "batch_size": 16,
#     "experiment_name": "ASIE_Week1"
#     # ... rest of your params
#     }

#     # The pipeline expects a list[dict]
#     pipeline_input = [config_from_file]

#     # Now it works with your function signature
#     output = retraining_pipeline(configs=pipeline_input)
#     print(f'Pipeline result: {output}')