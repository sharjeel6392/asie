# Business Logic Layer

import time
import torch
from constants import MAX_BATCH_SIZE

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

    def __init__(self, loader, logger):
        self.loader = loader
        self.logger = logger
    
    def predict(self, text):
        
        if isinstance(text, str):
            texts = [text]
        else:
            texts = text
        if len(texts) > MAX_BATCH_SIZE:
            raise ValueError(f'Batch size {len(texts)} exceeds max size of {MAX_BATCH_SIZE}')
        
        start = time.time()

        if not self.loader.is_ready():
            raise RuntimeError('Model not loaded')
        
        tokenizer = self.loader.tokenizer
        model = self.loader.model
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
                    'label': label_name,
                    'score': float(score.item())
                }
            )

            self.logger.log(
                text = texts[i],
                label = label_name,
                score = float(score.item()),
                latency_ms = 0.0,
            )
        latency_ms = (time.time() - start) * 1000
        result = {
            'predictions': predictions,
            'latency_ms': latency_ms
        }
        return result