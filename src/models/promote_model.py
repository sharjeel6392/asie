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

if __name__ == '__main__':
    promote(
        run_id='7eb939db74994011841608b40992a2a1',
        metrics = {'eval_f1': 0.9668874172185431, 'eval_loss': 0.1513603776693344},
        dataset = {'name': 'financial_phrasebank', 'version': 'v1'},
    )