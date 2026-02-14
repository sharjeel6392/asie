# The Control Plane

from fastapi import FastAPI, HTTPException
import mlflow
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

    print(f"Connected to MLflow at: {mlflow.get_tracking_uri()}")
    
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
        
        primary_pred = predictor.predict(req.text)
        predictions = primary_pred['predictions']
        latency_ms = primary_pred['latency_ms']

        per_sample_latency = latency_ms / len(predictions)

        # ----------------------------------------
        # Shadow Inference (None for now)
        # ----------------------------------------
        
        shadow_pred = None
        shadow_latency = None

        # ----------------------------------------
        # Comparison logic
        # ----------------------------------------
        
        disagreement = None
        abs_diff = None

        # if shadow_pred is not None:
        #     disagreement = int(primary_pred['predictions'] != shadow_pred)
        #     abs_diff = abs(float(primary_pred['predictions']) - float(shadow_pred))

        for text, pred in zip(req.text, predictions):

            record = {
                "request_id": str(uuid.uuid4()),
                "timestamp": datetime.now().isoformat(),
                "input_data": json.dumps({'text': text}),
                "true_label": None,

                "primary_model_name": "DistilBertForSequenceClassification",
                "primary_model_version": "v_01",
                "primary_prediction": float(pred['score']),
                "primary_latency_ms": per_sample_latency,

                "shadow_model_name": None,
                "shadow_model_version": None,
                "shadow_predictions": shadow_pred,
                "shadow_latency_ms": shadow_latency,

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
