# Lifecycle Management

from transformers import AutoTokenizer, AutoModelForSequenceClassification
from src.logger import logging

class ModelLoader:
    '''
    Loading models is expensive and must happen once, not per request.
    '''
    def __init__(self, device: str):
        self.device = device
        
        self.ready = False
        self.model = None
        self.tokenizer = None

    def load(self):
        """
        Load model + tokenizer here.
        """
        logging.info(f'Using device: {self.device}')

        try:
            self.tokenizer = AutoTokenizer.from_pretrained("./exported_model/tokenizer")
            self.model = AutoModelForSequenceClassification.from_pretrained("./exported_model/model")

            self.model.to(self.device)
            self.model.eval()

            self.ready = True

            logging.info(f'Model and Tokenizer loaded successfully.')
            
        except Exception as e:
            logging.exception(f'Unexpected error occured while loading model artifacts: {e}')
            self.ready = False
            raise
        
 
        # artifact_uri = os.path.normpath(os.path.join(self.mlruns_base, '1',self.run_id, 'artifacts'))
        # run_artifacts_path = mlflow.artifacts.download_artifacts(artifact_uri=artifact_uri)

        # # Resolve local paths ONLY
        # model_path = os.path.join(run_artifacts_path, 'model')
        # tokenizer_path = os.path.join(run_artifacts_path, 'tokenizer')
        # model_path = mlflow.artifacts.download_artifacts(artifact_uri=model_path)
        # if model_path is None:
        #     raise ValueError
        # tokenizer_path = mlflow.artifacts.download_artifacts(artifact_uri=tokenizer_path)

        # try:
        #     # Load from local filesystem
        #     self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_path)
        #     self.model = AutoModelForSequenceClassification.from_pretrained(model_path)

        #     self.model.to(self.device)
        #     self.model.eval()
        # except Exception as e:
        #     logging.error(f'Failed to load: {e}.')
        #     raise e
    
    def is_ready(self) -> bool:
        return self.ready