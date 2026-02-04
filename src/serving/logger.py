import mlflow
from src.constants import EXPERIMENT_NAME

class InferenceLogger:
    def __init__(self, model_run_id):
        self.model_run_id = model_run_id
        mlflow.set_experiment(EXPERIMENT_NAME)

    def log(self, *, text:str, label: str, score: float, latency_ms: float):
        with mlflow.start_run(run_name = 'inference', nested=False):
            mlflow.set_tag('type', 'inference')
            mlflow.set_tag('model_run_id', self.model_run_id)

            mlflow.log_metric('latency_ms', latency_ms)
            mlflow.log_metric('score', score)
            mlflow.log_metric('text_length', len(text))
            
            mlflow.set_tag('prediction', label)