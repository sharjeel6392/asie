# Lifecycle Management

import mlflow
import mlflow.tracking
import mlflow.artifacts
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

from logger import logging
from constants import EXPERIMENT_NAME

class ModelLoader:
    '''
    Loading models is expensive and must happen once, not per request.
    '''
    def __init__(self, model_uri, run_id, device = None):
        self.experiment_name = EXPERIMENT_NAME
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        self.model = None
        self.tokenizer = None
        self.run_id = run_id
        self.model_uri = model_uri

    def _get_latest_run(self):
        client = mlflow.tracking.MlflowClient()
        exp = client.get_experiment_by_name(self.experiment_name)

        if exp is None:
            raise RuntimeError(f"Experiment '{self.experiment_name}' not found.")

        runs = client.search_runs(
            experiment_ids = [exp.experiment_id],
            order_by = ['attributes.start_time DESC'],
            max_results = 1,
        )

        if not runs:
            raise RuntimeError('No MLflow runs found')
        
        return runs[0].info.run_id

    def load(self):
        """
        Load model + tokenizer here.
        """

        logging.info(f'Loading model from: {self.model_uri}')
        logging.info(f'Using device: {self.device}')

        model_local_path = mlflow.artifacts.download_artifacts(self.model_uri)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_local_path) #mlflow.pytorch.load_model(model_uri)
        self.model.to(self.device)
        self.model.eval()
        
        # If tokenizer was logged separately, load it. 
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_local_path)
            logging.info('Tokenizer loaded from model directory')
        except Exception as e:
            logging.warning(f'Could not load tokenizer from model path: {e}. Trying a separate download...')
            tokenizer_uri = f'runs:/{self.run_id}/tokenizer'
            tok_path = mlflow.artifacts.download_artifacts(tokenizer_uri)
            self.tokenizer = AutoTokenizer.from_pretrained(tok_path)
        
        logging.info(f'Model and tokenizer loaded successfully. Model ready: {self.is_ready()}')
    
    def is_ready(self):
        return self.model is not None and self.tokenizer is not None