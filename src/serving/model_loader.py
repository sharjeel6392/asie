# Lifecycle Management

from transformers import AutoTokenizer, AutoModelForSequenceClassification
from src.logger import logging
from src.serving.config import Settings

class ModelLoader:
    '''
    Loading models is expensive and must happen once, not per request.
    '''
    def __init__(self, device: str):
        self.device = device
        
        self.ready = False

        self.primary_model = None
        self.shadow_model = None

        self.primary_tokenizer = None
        self.shadow_tokenizer = None

    def load(self):
        """
        Load model + tokenizer here.
        """
        logging.info(f'Using device: {self.device}')

        try:
            self.primary_tokenizer = AutoTokenizer.from_pretrained(Settings.PRIMARY_TOKENIZER_PATH)
            self.primary_model = AutoModelForSequenceClassification.from_pretrained(Settings.PRIMARY_MODEL_PATH)
        except Exception as e:
            logging.exception(f'Unexpected error occured while loading model artifacts: {e}')
            self.ready = False
            raise
        try:
            self.shadow_tokenizer = AutoTokenizer.from_pretrained(Settings.SHADOW_TOKENIZER_PATH)
            self.shadow_model = AutoModelForSequenceClassification.from_pretrained(Settings.SHADOW_MODEL_PATH)

            self.shadow_model.to(self.device)
            self.shadow_model.eval()
        except Exception as e:
            logging.warning(f'Shadow model could not be loaded. Loading failed with exception: {e}')
            self.shadow_model = None
            self.shadow_tokenizer = None

        self.primary_model.to(self.device)
        self.primary_model.eval()

        self.ready = True

        logging.info(f'Model and Tokenizer loaded successfully.')
    
    def is_ready(self) -> bool:
        return self.primary_model is not None