# Lifecycle Management

import mlflow
from mlflow import tracking
import mlflow.artifacts
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from pathlib import Path
import os

from src.logger import logging
from src.constants import EXPERIMENT_NAME

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
        self.ready = False

    def load(self):
        """
        Load model + tokenizer here.
        """
        logging.info(f'Using device: {self.device}')

        mlflow.set_tracking_uri('file:/app/mlruns')
        logging.info(f'Loading model from run: {self.run_id}')
        print("A : Breaks here?")
        basePath =f'/app/mlruns/1/{self.run_id}/artifacts'
        run_artifacts_path = mlflow.artifacts.download_artifacts(basePath)
        print("B : Breaks here?")
        logging.info(f'Artifacts downloaded to {run_artifacts_path}')

        # Resolve local paths ONLY
        model_path = os.path.join(basePath, 'model')
        tokenizer_path = os.path.join(basePath, 'tokenizer')

        logging.info(f"Model dir contents: {os.listdir(model_path)}")
        logging.info(f"Tokenizer dir contents: {os.listdir(tokenizer_path)}")

        try:
            # Load from local filesystem
            self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_path)
            print("C: Breaks here?")
            self.model = AutoModelForSequenceClassification.from_pretrained(model_path)
            print("D : Breaks here?")

            self.model.to(self.device)
            self.model.eval()
        except Exception as e:
            logging.error(f'Failed to load: {e}.')
            raise e
        
        logging.info(f'Model and tokenizer loaded successfully. Model ready: {self.is_ready()}')
        self.ready = True
    
    def is_ready(self):
        return self.ready