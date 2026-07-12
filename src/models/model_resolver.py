import yaml
from src.constants import MODEL_REGISTRY_FILE, PROMOTED_MODEL_STATE


def get_promoted_model():
    with open(MODEL_REGISTRY_FILE) as f:
        registry = yaml.safe_load(f)

    promoted = [
        m for m in registry['models']
        if m['state'] == PROMOTED_MODEL_STATE
    ]

    if not promoted:
        raise RuntimeError('No promoted model found')
    
    return sorted(
        promoted,
        key = lambda x: x['created_at'],
        reverse = True
    )

# if __name__ == '__main__':
#     print(get_promoted_model())