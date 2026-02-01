# Lifecycle Management

import mlflow
import mlflow.artifacts
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

from logger import logging
from constants import EXPERIMENT_NAME
from models.model_resolver import get_promoted_model

class ModelLoader:
    '''
    Loading models is expensive and must happen once, not per request.
    '''
    def __init__(self, device = None):
        self.experiment_name = EXPERIMENT_NAME
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        self.model = None
        self.tokenizer = None
        self.run_id = None

    def load(self):
        """
        Load model + tokenizer here.
        """
        model_info = get_promoted_model()
        model_uri = f'runs:/{model_info['run_id']}/model'
        run_id = model_info['run_id']
        logging.info(f'Loaded model is: {model_info}')

        logging.info(f'Loading model from: {model_uri}')
        logging.info(f'Using device: {self.device}')

        self.run_id = run_id

        model_local_path = mlflow.artifacts.download_artifacts(model_uri)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_local_path) #mlflow.pytorch.load_model(model_uri)
        self.model.to(self.device)
        self.model.eval()
        
        # If tokenizer was logged separately, load it. 
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_local_path)
            logging.info('Tokenizer loaded from model directory')
        except Exception as e:
            logging.warning(f'Could not load tokenizer from model path: {e}. Trying a separate download...')
            tokenizer_uri = f'runs:/{run_id}/tokenizer'
            tok_path = mlflow.artifacts.download_artifacts(tokenizer_uri)
            self.tokenizer = AutoTokenizer.from_pretrained(tok_path)
        
        logging.info(f'Model and tokenizer loaded successfully. Model ready: {self.is_ready()}')
    
    def is_ready(self):
        return self.model is not None and self.tokenizer is not None