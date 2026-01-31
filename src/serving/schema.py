# This module generates API contracts

from pydantic import BaseModel
'''
    Pydantic is used here to:
    - Validate user input
    - Reject bad requests
    - Generate Swagger docs
'''
from typing import List, Optional

class PredictRequest(BaseModel):
    '''
    This defines "What must a client send me?"
    '''
    text: str

class PredictResponse(BaseModel):
    '''
        It guarantees:
        - Shape of output
        - Docs auto-generation
        - Client consistency
    '''
    label: str
    score: float
    model_version: Optional[str] = None
    latency_ms: Optional[float] = None