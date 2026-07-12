import os
import shutil
import mlflow
from mlflow import artifacts

from src.models.model_registry import load_registry
from src.serving.config import Settings
from src.logger import configure_logger
from src.constants import EXPORTED_MODEL_DIR, MODEL_DIR_NAME, TOKENIZER_DIR_NAME


def _download(run_id: str, artifact_path: str) -> str:
    uri = f'runs:/{run_id}/{artifact_path}'
    return artifacts.download_artifacts(uri)

def _copy(src, dst):
    shutil.copytree(src, dst)

def export_models():
    logger = configure_logger()
    registry = load_registry()

    mlflow.set_tracking_uri(Settings.MLFLOW_TRACKING_URI)

    if os.path.exists(EXPORTED_MODEL_DIR):
        shutil.rmtree(EXPORTED_MODEL_DIR)

    os.makedirs(EXPORTED_MODEL_DIR, exist_ok=True)

    # Export Primary
    primary = registry.get('primary')

    if not primary:
        raise ValueError('No primary model found in registry')
    
    logger.debug('Exporting Primary mode...')

    model_path = _download(primary['run_id'], 'model')
    tokenizer_path = _download(primary['run_id'], "tokenizer")

    _copy(model_path, os.path.join(EXPORTED_MODEL_DIR, 'primary', 'model'))
    _copy(tokenizer_path, os.path.join(EXPORTED_MODEL_DIR, 'primary', 'tokenizer'))

    # Export Shadow (if exists)
    shadow = registry.get('shadow')

    if shadow:
        logger.debug('Exporting shadow model...')

        model_path = _download(shadow['run_id'], 'model')
        tokenizer_path = _download(shadow['run_id'], 'tokenizer')

        _copy(model_path, os.path.join(EXPORTED_MODEL_DIR, "shadow", MODEL_DIR_NAME))
        _copy(tokenizer_path, os.path.join(EXPORTED_MODEL_DIR, 'shadow', TOKENIZER_DIR_NAME))
    
    logger.debug('Export complete')


# if __name__ == '__main__':
#     export_models()