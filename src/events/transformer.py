from datetime import datetime
from src.drift.storage.drift_metrics_repository import get_latest_drift_metric
from src.events.schema import DriftEvent

def transform_alert_to_event(alert: dict, status: str) -> DriftEvent:
    labels = alert.get("labels", {})

    return {
        "event_type": "DRIFT_DETECTED",
        "timestamp": datetime.now().isoformat(),
        "status": status,
        "alert_name": labels.get("alertname", "unknown"),
        "severity": labels.get("severity", "unknown"),
        "drift_score": get_latest_drift_metric()
    }