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

        self.primary_model = None
        self.shadow_model = None

        self.tokenizer = None

    def load(self):
        """
        Load model + tokenizer here.
        """
        logging.info(f'Using device: {self.device}')

        try:
            self.tokenizer = AutoTokenizer.from_pretrained("./exported_model/tokenizer")

            self.primary_model = AutoModelForSequenceClassification.from_pretrained("./exported_model/model")
            self.shadow_model = AutoModelForSequenceClassification.from_pretrained("./exported_model/model")

            self.primary_model.to(self.device)
            self.primary_model.eval()

            self.shadow_model.to(self.device)
            self.shadow_model.eval()

            self.ready = True

            logging.info(f'Model and Tokenizer loaded successfully.')
            
        except Exception as e:
            logging.exception(f'Unexpected error occured while loading model artifacts: {e}')
            self.ready = False
            raise
    
    def is_ready(self) -> bool:
        return self.ready