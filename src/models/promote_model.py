import yaml
from datetime import datetime
from src.constants import (
    DATASET_VERSION,
    DEFAULT_MODEL_NAME,
    MODEL_REGISTRY_FILE,
    PROMOTED_MODEL_STATE,
)

def promote(run_id, metrics, dataset):
    registry_path = MODEL_REGISTRY_FILE

    with open(registry_path) as f:
        registry = yaml.safe_load(f) or {'models': []}
    
    entry = {
        'name': DEFAULT_MODEL_NAME,
        'version': DATASET_VERSION,
        'run_id': run_id,
        'dataset': dataset,
        'metrics': metrics,
        'state': PROMOTED_MODEL_STATE,
        'created_at': datetime.now().isoformat(),
    }

    registry['models'].append(entry)
    with open (registry_path, 'w') as f:
        yaml.safe_dump(registry, f)
