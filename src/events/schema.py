from typing import TypedDict

class DriftEvent(TypedDict):
    event_type: str
    timestamp: str
    status: str
    alert_name: str
    severity: str
    drift_score: float