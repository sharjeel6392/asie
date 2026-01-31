from pydantic import BaseModel
from typing import List, Optional

class PredictRequest(BaseModel):
    text: str

class PredictResponse(BaseModel):
    label: str
    score: float
    model_version: Optional[str] = None
    latency_ms: Optional[float] = None