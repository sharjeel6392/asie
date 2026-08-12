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

def _sync_exported_model_to_s3(logger) -> None:
    """Uploads EXPORTED_MODEL_DIR to S3 so the serving pods' initContainer
    has something fresh to fetch on next restart/scale-out. Gated on
    ASIE_MODEL_S3_URI — no-op locally (matches model_registry.py's gating)."""
    s3_uri = os.getenv("ASIE_MODEL_S3_URI")
    if not s3_uri:
        return

    import boto3

    bucket, _, prefix = s3_uri.rstrip('/').partition('/')
    s3 = boto3.client("s3")

    for root, _dirs, files in os.walk(EXPORTED_MODEL_DIR):
        for filename in files:
            if filename == "training_args.bin":
                continue  # never read by from_pretrained(), pure dead weight
            local_path = os.path.join(root, filename)
            rel_path = os.path.relpath(local_path, EXPORTED_MODEL_DIR)
            key = f"{prefix}/{rel_path}".replace(os.sep, "/")
            s3.upload_file(local_path, bucket, key)

    logger.debug(f'Synced {EXPORTED_MODEL_DIR} -> s3://{bucket}/{prefix}/')

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

    _sync_exported_model_to_s3(logger)

    logger.debug('Export complete')


# if __name__ == '__main__':
#     export_models()