# Business Logic Layer

import time
import torch

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
    
    def predict(self, text: str):
        start = time.time()

        if not self.loader.is_ready():
            raise RuntimeError('Model not loaded')
        
        tokenizer = self.loader.tokenizer
        model = self.loader.model
        device = self.loader.device

        inputs = tokenizer(
            text, 
            return_tensors = 'pt',
            truncation=True, 
            padding=True,
            max_length = 256
        )
        inputs = {k: v.to(device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = model(**inputs)
            logits = outputs.logits if hasattr(outputs, 'logits') else outputs[0]
            probs = torch.softmax(logits, dim=-1)

        score, idx = torch.max(probs, dim = -1)

        latency_ms = (time.time() - start) * 1000

        label_name = model.config.id2label[idx.item()]
        print(f"LABEL_NAME: {label_name}")

        result = {
            'label': label_name,
            'score': float(score.item()),
            'latency_ms': latency_ms,
        }
        
        self.logger.log(
            text = text,
            label = label_name,
            score = float(score.item()),
            latency_ms = latency_ms,
            model_run_id = self.loader.run_id,
        )

        return result