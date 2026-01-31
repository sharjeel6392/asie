from fastapi import FastAPI, HTTPException
from src.serving.schema import PredictRequest, PredictResponse
from src.serving.model_loader import ModelLoader
from src.serving.predictor import Predictor
from src.logger import logging

app = FastAPI(title= 'ASIE Serving API')

loader = ModelLoader()
predictor = Predictor(loader=loader)

@app.on_event('startup')
def startup_event():
    loader.load()

@app.get('/health')
def health():
    return {'status': 'ok', 'model_loader': loader.is_ready()}

@app.post('/predict', response_model=PredictResponse)
def predict(req: PredictRequest):
    try:
        result = predictor.predict(req.text)
        return PredictResponse(**result, model_version = 'v0')
    except Exception as e:
        logging.error(f'Unexpected error occured while predicting: {e}')
        raise HTTPException(status_code=500)
