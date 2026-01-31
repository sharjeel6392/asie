import mlflow
import time
from constants import EXPERIMENT_NAME

class InferenceLogger:
    def __init__(self):
        mlflow.set_experiment(EXPERIMENT_NAME)

    def log(self, *, text, label, score, latency_ms, model_run_id):
        with mlflow.start_run(nested=False):
            mlflow.set_tag('type', 'inference')
            mlflow.set_tag('model_run_id', model_run_id)

            mlflow.log_metric('latency_ms', latency_ms)
            mlflow.log_metric('score', score)
            mlflow.log_param('text_length', len(text))
            
            mlflow.log_param('prediction', label)