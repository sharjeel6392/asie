# The Control Plane

from fastapi import FastAPI, HTTPException

from src.serving.schema import PredictRequest, PredictResponse
from src.serving.model_loader import ModelLoader
from src.serving.predictor import Predictor
from src.logger import logging
from src.serving.logger import InferenceLogger
from src.models.model_resolver import get_promoted_model


app = FastAPI(title= 'ASIE Serving API')

loader = None
predictor = None

@app.on_event('startup')
def startup_event():
    '''
    This tells FastAPI "Whenever the server starts, prepare the model."
    This ensures:
    - Model loads once
    - Memory is prepared
    - Server is warm
    '''
    global predictor, loader
    model_info = get_promoted_model()
    run_id = model_info['run_id']
    model_uri = f'/app/mlruns/1/{run_id}/artifacts/model'
    loader = ModelLoader(model_uri = model_uri, run_id = run_id)

    loader.load()
    app.state.model_ready = True
    logger = InferenceLogger(model_run_id=run_id)
    predictor = Predictor(loader = loader, logger=logger)

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
        'model_loader': loader is not None and loader.is_ready(),
        'device': loader.device if loader else None,
        'run_id': loader.run_id if loader else None,
        }

@app.post('/predict', response_model=PredictResponse)
async def predict(req: PredictRequest):
    '''
    Prediction endpoint; a public interface
    '''
    if predictor is None:
        raise HTTPException(status_code=503, detail = 'Model not loaded')
    try:
        result = predictor.predict(req.text)
        return PredictResponse(
            predictions = result['predictions'],
            latency_ms= result['latency_ms'],
            model_version= 'v0'
        )
    except Exception as e:
        logging.error(f'Unexpected error occured while predicting: {e}')
        raise HTTPException(status_code=500)
