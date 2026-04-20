# The Control Plane

from fastapi import FastAPI, HTTPException, Response, Request
import uuid
from datetime import datetime
import json
from prometheus_client import Gauge, generate_latest

from src.serving.schema import PredictRequest, PredictResponse
from src.serving.model_loader import ModelLoader
from src.serving.predictor import Predictor
from src.logger import logging
from src.serving.config import Settings
from src.serving.inference_log_DB.database import init_db
from src.serving.inference_log_DB.repository import log_inference
from src.drift.worker import run_drift_job
from src.drift.storage.drift_metrics_repository import get_latest_drift_metric


app = FastAPI(title= 'ASIE Serving API')
loader = ModelLoader(device="cpu")
predictor = None

drift_gauge = Gauge(
    "asie_data_drift_score",
    "Aggregated drift score (feature + prediction drift)"
)

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
        'primary_ready': loader.primary_model is not None,
        'shadow_ready': loader.shadow_model is not None,
        'shadow_model_object': str(type(loader.shadow_model)),
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
    
    except Exception as e:
        logging.critical(f'Primary model failed to load: {e}')
        raise # Hard Fail

    # ----------------------------------------
    # Shadow Inference (optional)
    # ----------------------------------------
    shadow_predictions = None
    shadow_per_sample_latency = None
    shadow_enabled = False

    if loader.shadow_model is not None:
        shadow_enabled = True
        try:
            shadow_preds = predictor.predict(req.text, "shadow")
            shadow_predictions = shadow_preds['predictions']
            shadow_latency = shadow_preds['latency_ms']
            shadow_per_sample_latency = shadow_latency / len(shadow_predictions)            
        except Exception as e:
            logging.error(f'Shadow failed: {e}')
            shadow_predictions = [None] * len(req.text)
            shadow_per_sample_latency = None

    # ----------------------------------------
    # Comparison logic
    # ----------------------------------------

    for i, text in enumerate(req.text):
        primary = primary_predictions[i]
        embeddings = primary.get("embedding", None)
        shadow = (shadow_predictions[i] if shadow_predictions and i < len(shadow_predictions) else None)

        disagreement = None
        abs_diff = None

        if shadow is not None:
            disagreement = int(primary['label'] != shadow['label'])
            abs_diff = abs(float(primary['score'] - shadow['score']))


        record = {
            "request_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "input_data": json.dumps({'text': text}),
            "embedding_json": json.dumps(embeddings) if embeddings else None,
            "input_length": len(text),
            "true_label": None,

            "primary_model_name": "DistilBertForSequenceClassification",
            "primary_model_version": "v_01",
            "primary_prediction": primary['label'],
            "primary_confidence": primary['score'],
            "primary_latency_ms": primary_per_sample_latency,

            "shadow_model_name": "DistilBertForSequenceClassification" if shadow_enabled else None,
            "shadow_model_version": 'v_02' if shadow_enabled else None,
            "shadow_predictions": shadow['label'] if shadow else None,
            "shadow_confidence": shadow['score'] if shadow else None,
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

@app.get("/drift")
def get_drift():
    result = run_drift_job(window_hours=24)
    return result

@app.get("/metrics")
def metrics():
    drift_value = get_latest_drift_metric()
    drift_gauge.set(drift_value)

    return Response(generate_latest(), media_type="text/plain")

@app.post("/webhook")
async def webhook_receiver(request: Request):
    try:
        payload = await request.json()
    except Exception:
        payload = {"error": "invalid json"}

    print("ALERT RECEIVED")
    print(payload)

    return {"status": "received"}