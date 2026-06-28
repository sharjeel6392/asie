import traceback

from src.experiments.runner import run_experiments
from src.experiments.selector import select_best_model
from src.models.model_registry import register_shadow_model
from src.models.export_model import export_models
from src.logger import configure_logger

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

        logger.info("Retraining pipeline completed successfully.")

        return {
            "status": "success",
            "run_id": best_model.get('run_id'),
            "metrics": best_model.get('metrics')

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