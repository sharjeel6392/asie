# The Control Plane

from fastapi import FastAPI, HTTPException
from serving.schema import PredictRequest, PredictResponse
from serving.model_loader import ModelLoader
from serving.predictor import Predictor
from logger import logging
from serving.logger import InferenceLogger

app = FastAPI(title= 'ASIE Serving API')

loader = ModelLoader()
logger = InferenceLogger()
predictor = Predictor(loader=loader, logger= logger)

@app.on_event('startup')
def startup_event():
    '''
    This tells FastAPI "Whenever the server starts, prepare the model."
    This ensures:
    - Model loads once
    - Memory is prepared
    - Server is warm
    '''
    loader.load()

@app.get('/health')
def health():
    '''
    This will be used for:
    - Kubernetes readiness checks
    - uptime monitoring
    - debugging
    It basically answers "is ASIE alive and ready?"
    '''
    return {
        'status': 'ok', 
        'model_loader': loader.is_ready(),
        'device': loader.device,
        'run_id': loader.run_id,
        }

@app.post('/predict', response_model=PredictResponse)
def predict(req: PredictRequest):
    '''
    Prediction endpoint; a public interface
    '''
    try:
        result = predictor.predict(req.text)
        return PredictResponse(**result, model_version = 'v0')
    except Exception as e:
        logging.error(f'Unexpected error occured while predicting: {e}')
        raise HTTPException(status_code=500)
