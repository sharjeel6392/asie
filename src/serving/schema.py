# This module generates API contracts

from pydantic import BaseModel
'''
    Pydantic is used here to:
    - Validate user input
    - Reject bad requests
    - Generate Swagger docs
'''
from typing import List, Optional, Union

class PredictRequest(BaseModel):
    '''
    This defines "What must a client send me?"
    '''
    text: Union[str, List[str]]

class Prediction(BaseModel):
    label: str
    score: float

class PredictResponse(BaseModel):
    '''
        It guarantees:
        - Shape of output
        - Docs auto-generation
        - Client consistency
    '''
    predictions: List[Prediction]
    model_version: Optional[str] = None
    latency_ms: Optional[float] = None