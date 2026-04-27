import os
import shutil
import mlflow
from mlflow import tracking
from mlflow import artifacts

from src.models.model_registry import load_registry
from serving.config import Settings

EXPORT_DIR = "exported_model"

def _download(run_id: str, artifact_path: str) -> str:
    uri = f'runs:/{run_id}/{artifact_path}'
    return artifacts.download_artifacts(uri)

def _copy(src, dst):
    shutil.copytree(src, dst)

def export_models():
    registry = load_registry()

    mlflow.set_tracking_uri(Settings.MLFLOW_TRACKING_URI)

    if os.path.exists(EXPORT_DIR):
        shutil.rmtree(EXPORT_DIR)

    os.makedirs(EXPORT_DIR, exist_ok=True)

    # Export Primary
    primary = registry.get('primary')

    if not primary:
        raise ValueError('No primary model found in registry')
    
    print('Exporting Primary mode...')

    model_path = _download(primary['run_id'], 'model')
    tokenizer_path = _download(primary['run_id'], "tokenizer")

    _copy(model_path, os.path.join(EXPORT_DIR, 'primary', 'model'))
    _copy(tokenizer_path, os.path.join(EXPORT_DIR, 'primary', 'tokenizer'))

    # Export Shadow (if exists)
    shadow = registry.get('shadow')

    if shadow:
        print('Exporting shadow model...')

        model_path = _download(shadow['run_id'], 'model')
        tokenizer_path = _download(shadow['run_id'], 'tokenizer')

        _copy(model_path, os.path.join(EXPORT_DIR, "shadow", "model"))
        _copy(tokenizer_path, os.path.join(EXPORT_DIR, 'shadow', 'tokenizer'))
    
    print('Export complete')


if __name__ == '__main__':
    export_models()