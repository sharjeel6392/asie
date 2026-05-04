from typing import TypedDict, Optional

class ExperimentResult(TypedDict, total=False):
    run_id: Optional[str]
    metrics: dict
    evaluation: dict
    status: str
    config: dict
    data_hash: str
    timestamp: str
    failure_reason: Optional[str]
    error: Optional[str]