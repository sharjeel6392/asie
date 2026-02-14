# Business Logic Layer

import time
import torch
from src.constants import MAX_BATCH_SIZE
from src.logger import logging

class Predictor:
    '''
    This is the core inference abstraction.
    It isolates:
    - Preprocessing
    - Model forward pass
    - Postprocessing
    - Latency measurement
    away from HTTP
    '''

    def __init__(self, loader):
        self.loader = loader
    
    def predict(self, text, model_type: str = 'primary'):
        
        if isinstance(text, str):
            texts = [text]
        else:
            texts = text
        if len(texts) > MAX_BATCH_SIZE:
            raise ValueError(f'Batch size {len(texts)} exceeds max size of {MAX_BATCH_SIZE}')
        
        start = time.time()

        if not self.loader.is_ready():
            raise RuntimeError('Model not loaded')
        
        if model_type == 'primary':
            model = self.loader.primary_model
            tokenizer = self.loader.primary_tokenizer
        elif model_type == 'shadow':
            model = self.loader.shadow_model
            tokenizer = self.loader.shadow_tokenizer
        else:
            logging.error("Model type invalid")
            raise
        device = self.loader.device

        inputs = tokenizer(
            texts, 
            return_tensors = 'pt',
            truncation=True, 
            padding=True,
        )
        inputs = {k: v.to(device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = model(**inputs)
            logits = outputs.logits if hasattr(outputs, 'logits') else outputs[0]
            probs = torch.softmax(logits, dim=-1)
        predictions = []
        for i, prob in enumerate(probs):
            score, idx = torch.max(prob, dim = -1)
            label_name = model.config.id2label[idx.item()]
            
            predictions.append(
                {
                    'text': texts,
                    'label': label_name,
                    'score': float(score.item())
                }
            )

        latency_ms = (time.time() - start) * 1000
        result = {
            'predictions': predictions,
            'latency_ms': latency_ms
        }
        return result