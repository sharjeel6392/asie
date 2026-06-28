import yaml
from datetime import datetime

def promote(run_id, metrics, dataset):
    registry_path = "model/model_registry.yaml"

    with open(registry_path) as f:
        registry = yaml.safe_load(f) or {'models': []}
    
    entry = {
        'name': 'asie-sentiment',
        'version': 'v1',
        'run_id': run_id,
        'dataset': dataset,
        'metrics': metrics,
        'state': 'promoted',
        'created_at': datetime.now().isoformat(),
    }

    registry['models'].append(entry)
    with open (registry_path, 'w') as f:
        yaml.safe_dump(registry, f)
