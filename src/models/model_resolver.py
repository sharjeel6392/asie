import yaml

def get_promoted_model():
    with open('model/model_registry.yaml') as f:
        registry = yaml.safe_load(f)

    promoted = [
        m for m in registry['models']
        if m['state'] == 'promoted'
    ]

    if not promoted:
        raise RuntimeError('No promoted model found')
    
    return sorted(
        promoted,
        key = lambda x: x['created_at'],
        reverse = True
    )

if __name__ == '__main__':
    print(get_promoted_model())