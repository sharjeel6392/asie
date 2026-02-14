# The Control Plane

from fastapi import FastAPI, HTTPException
import uuid
from datetime import datetime
import json

from src.serving.schema import PredictRequest, PredictResponse
from src.serving.model_loader import ModelLoader
from src.serving.predictor import Predictor
from src.logger import logging
from src.serving.config import Settings
from src.serving.inference_log_DB.database import init_db
from src.serving.inference_log_DB.repository import log_inference


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
    logging.info(f'Connecting to the inference db...')
    connected = init_db()
    if connected == False:
        logging.error("No connection to the inference log db")
        raise
    
    loader = ModelLoader(
        device= Settings.INFERENCE_DEVICE,
    )

    loader.load()
    predictor = Predictor(loader = loader)

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
        }



@app.post('/predict', response_model=PredictResponse)
async def predict(req: PredictRequest):
    '''
    Prediction endpoint; a public interface
    '''
    if predictor is None:
        raise HTTPException(status_code=503, detail = 'Model not loaded')
    try:
        # ----------------------------------------
        # Primary Inference
        # ----------------------------------------
        
        primary_pred = predictor.predict(req.text, "primary")
        primary_predictions = primary_pred['predictions']
        latency_ms = primary_pred['latency_ms']

        primary_per_sample_latency = latency_ms / len(primary_predictions)

        # ----------------------------------------
        # Shadow Inference (None for now)
        # ----------------------------------------
        
        try:
            shadow_preds = predictor.predict(req.text, "shadow")
            shadow_predictions = shadow_preds['predictions']
            shadow_latency = shadow_preds['latency_ms']
            shadow_per_sample_latency = shadow_latency / len(shadow_predictions)            
        except Exception as e:
            logging.error(f'Shadow failed: {e}')
            shadow_predictions = [{'predictions': {}, latency_ms: 0}] * len(req.text)
            shadow_per_sample_latency = 0

        # ----------------------------------------
        # Comparison logic
        # ----------------------------------------
        
        disagreement = None
        abs_diff = None

        for i, text in enumerate(req.text):
            primary = primary_predictions[i]
            shadow = shadow_predictions[i]

            if shadow is not None:
                disagreement = int(primary['score'] != shadow['score'])
                abs_diff = abs(float(primary['score'] - shadow['score']))


            record = {
                "request_id": str(uuid.uuid4()),
                "timestamp": datetime.now().isoformat(),
                "input_data": json.dumps({'text': text}),
                "true_label": None,

                "primary_model_name": "DistilBertForSequenceClassification",
                "primary_model_version": "v_01",
                "primary_prediction": primary['label'],
                "primary_latency_ms": primary_per_sample_latency,

                "shadow_model_name": "DistilBertForSequenceClassification",
                "shadow_model_version": 'v_02',
                "shadow_predictions": shadow['label'],
                "shadow_latency_ms": shadow_per_sample_latency,

                "disagreement": disagreement,
                "abs_diff": abs_diff,

                "request_source": "api"
            }
            log_inference(record)

        return PredictResponse(
            predictions = primary_pred['predictions'],
            latency_ms= primary_pred['latency_ms'],
            model_version= 'v0'
        )
    except Exception as e:
        logging.error(f'Unexpected error occured while predicting: {e}')
        raise HTTPException(status_code=500)
