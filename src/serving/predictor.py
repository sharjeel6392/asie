import time

class Predictor:
    def __init__(self, loader):
        self.loader = loader
    
    def predict(self, text: str):
        start = time.time()

        if not self.loader.is_ready():
            raise RuntimeError('Model not loaded')
        
        # Stub prediction
        label = "neutral"
        score = 0.5

        latency_ms = (time.time() - start) * 1000

        return {
            'label': label,
            'score': score,
            'latency_ms': latency_ms
        }