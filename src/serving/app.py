# The Control Plane

from fastapi import FastAPI, HTTPException, Response, Request
import uuid
from datetime import datetime
import json
from prometheus_client import Gauge, generate_latest

from src.serving.schema import PredictRequest, PredictResponse
from src.serving.model_loader import ModelLoader
from src.serving.predictor import Predictor
from src.logger import configure_logger
from src.serving.config import Settings
from src.serving.inference_log_DB.database import init_db
from src.drift.storage.drift_metrics_repository import init_drift_db as storage_db
from src.serving.inference_log_DB.repository import log_inference
from src.drift.worker import run_drift_job
from src.drift.storage.drift_metrics_repository import get_latest_drift_metric
from src.events.transformer import transform_alert_to_event
from src.constants import (
    API_TITLE,
    DEFAULT_DRIFT_WINDOW_HOURS,
    DEFAULT_INFERENCE_DEVICE,
    DRIFT_METRIC_DESCRIPTION,
    DRIFT_METRIC_NAME,
    DRIFT_ROUTE,
    DRIFT_WEBHOOK_ROUTE,
    HEALTH_ROUTE,
    METRICS_ROUTE,
    MODEL_CLASS_NAME,
    PREDICT_ROUTE,
    PRIMARY_MODEL_ROLE,
    PRIMARY_MODEL_VERSION,
    PROMETHEUS_TEXT_MEDIA_TYPE,
    REQUEST_SOURCE_API,
    SERVED_MODEL_VERSION,
    SHADOW_MODEL_ROLE,
    SHADOW_MODEL_VERSION,
    WEBHOOK_ROUTE,
)


app = FastAPI(title= API_TITLE)
loader = ModelLoader(device=DEFAULT_INFERENCE_DEVICE)
predictor = None
storage_db()

drift_gauge = Gauge(
    DRIFT_METRIC_NAME,
    DRIFT_METRIC_DESCRIPTION
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
    logger = configure_logger()
    global predictor, loader
    logger.info(f'Connecting to the inference db...')
    connected = init_db()
    if connected == False:
        logger.error("No connection to the inference log db")
        raise
    
    loader = ModelLoader(
        device= Settings.INFERENCE_DEVICE,
    )

    loader.load()
    predictor = Predictor(loader = loader)

@app.get(HEALTH_ROUTE)
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



@app.post(PREDICT_ROUTE, response_model=PredictResponse)
async def predict(req: PredictRequest):
    '''
    Prediction endpoint; a public interface
    '''
    logger = configure_logger()
    if predictor is None:
        raise HTTPException(status_code=503, detail = 'Model not loaded')
    try:
        # ----------------------------------------
        # Primary Inference
        # ----------------------------------------
        
        primary_pred = predictor.predict(req.text, PRIMARY_MODEL_ROLE)
        primary_predictions = primary_pred['predictions']
        latency_ms = primary_pred['latency_ms']

        primary_per_sample_latency = latency_ms / len(primary_predictions)
    
    except Exception as e:
        logger.critical(f'Primary model failed to load: {e}')
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
            shadow_preds = predictor.predict(req.text, SHADOW_MODEL_ROLE)
            shadow_predictions = shadow_preds['predictions']
            shadow_latency = shadow_preds['latency_ms']
            shadow_per_sample_latency = shadow_latency / len(shadow_predictions)            
        except Exception as e:
            logger.error(f'Shadow failed: {e}')
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

            "primary_model_name": MODEL_CLASS_NAME,
            "primary_model_version": PRIMARY_MODEL_VERSION,
            "primary_prediction": primary['label'],
            "primary_confidence": primary['score'],
            "primary_latency_ms": primary_per_sample_latency,

            "shadow_model_name": MODEL_CLASS_NAME if shadow_enabled else None,
            "shadow_model_version": SHADOW_MODEL_VERSION if shadow_enabled else None,
            "shadow_predictions": shadow['label'] if shadow else None,
            "shadow_confidence": shadow['score'] if shadow else None,
            "shadow_latency_ms": shadow_per_sample_latency,

            "disagreement": disagreement,
            "abs_diff": abs_diff,

            "request_source": REQUEST_SOURCE_API
        }
        log_inference(record)

    return PredictResponse(
        predictions = primary_pred['predictions'],
        latency_ms= primary_pred['latency_ms'],
        model_version= SERVED_MODEL_VERSION
    )

@app.get(DRIFT_ROUTE)
def get_drift():
    result = run_drift_job(window_hours=DEFAULT_DRIFT_WINDOW_HOURS)
    return result

@app.get(METRICS_ROUTE, response_class=Response)
def metrics():
    drift_value = get_latest_drift_metric()
    drift_gauge.set(drift_value)

    return Response(generate_latest(), media_type=PROMETHEUS_TEXT_MEDIA_TYPE)

@app.post(WEBHOOK_ROUTE)
async def webhook_receiver(request: Request):
    try:
        payload = await request.json()
    except Exception:
        payload = {"error": "invalid json"}

    print("ALERT RECEIVED")
    print(payload)

    return {"status": "received"}

@app.post(DRIFT_WEBHOOK_ROUTE)
async def drift_webhook(request: Request):
    payload = await request.json()

    events = []

    for alert in payload.get("alerts", []):
        event = transform_alert_to_event(alert, payload.get("status"))
        events.append(event)

        print("DRIFT EVENT")
        print(event)

    return {"events_processed": len(events)}