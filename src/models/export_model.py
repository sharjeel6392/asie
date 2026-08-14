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

def _sync_model_version_to_s3(logger, run_id: str, local_dir: str) -> None:
    """Upload one model version to its OWN S3 prefix: models/<run_id>/.

    This layout is what makes rollback possible. The previous version wrote
    every export to a fixed models/primary/ and models/shadow/, overwriting in
    place. Reverting a model version in git would then restart the pods, they
    would re-sync that same prefix, and get back the weights that had just
    overwritten the ones being rolled back to -- the revert appeared to work
    and changed nothing, because the older bytes no longer existed anywhere.

    Keyed by MLflow run_id, exports are append-only and a version pointer in
    gitops/values/inference.yaml addresses real, immutable content.

    Gated on ASIE_MODEL_S3_URI -- no-op locally (matches model_registry.py).

    NOTE: prefixes accumulate at roughly 250 MB per model per retrain. An S3
    lifecycle expiry on models/ is required before this runs unattended for
    long; see DEPLOYMENT_ARCHITECTURE.md §6.1.
    """
    s3_uri = os.getenv("ASIE_MODEL_S3_URI")
    if not s3_uri:
        return

    import boto3

    bucket, _, prefix = s3_uri.rstrip('/').partition('/')
    version_prefix = f"{prefix}/{run_id}"
    s3 = boto3.client("s3")

    # Already uploaded: skip. A run_id prefix is immutable by construction, so
    # its presence means the content is there. Without this, promoting a model
    # that is already the shadow re-uploads ~250 MB for no reason, and the
    # primary/shadow pair pointing at one run would upload it twice.
    existing = s3.list_objects_v2(Bucket=bucket, Prefix=f"{version_prefix}/", MaxKeys=1)
    if existing.get("KeyCount", 0) > 0:
        logger.debug(f'Version {run_id} already in s3://{bucket}/{version_prefix}/ — skipping upload')
        return

    uploaded = 0
    for root, _dirs, files in os.walk(local_dir):
        for filename in files:
            if filename == "training_args.bin":
                continue  # never read by from_pretrained(), pure dead weight
            local_path = os.path.join(root, filename)
            rel_path = os.path.relpath(local_path, local_dir)
            key = f"{version_prefix}/{rel_path}".replace(os.sep, "/")
            s3.upload_file(local_path, bucket, key)
            uploaded += 1

    logger.debug(f'Synced {local_dir} -> s3://{bucket}/{version_prefix}/ ({uploaded} files)')

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

    primary_dir = os.path.join(EXPORTED_MODEL_DIR, 'primary')
    model_path = _download(primary['run_id'], 'model')
    tokenizer_path = _download(primary['run_id'], "tokenizer")

    _copy(model_path, os.path.join(primary_dir, MODEL_DIR_NAME))
    _copy(tokenizer_path, os.path.join(primary_dir, TOKENIZER_DIR_NAME))

    # Uploaded under the run_id, not under "primary". The role a model plays
    # is a deployment decision recorded in git; S3 only stores content.
    _sync_model_version_to_s3(logger, primary['run_id'], primary_dir)

    # Export Shadow (if exists)
    shadow = registry.get('shadow')

    if shadow:
        logger.debug('Exporting shadow model...')

        shadow_dir = os.path.join(EXPORTED_MODEL_DIR, 'shadow')
        model_path = _download(shadow['run_id'], 'model')
        tokenizer_path = _download(shadow['run_id'], 'tokenizer')

        _copy(model_path, os.path.join(shadow_dir, MODEL_DIR_NAME))
        _copy(tokenizer_path, os.path.join(shadow_dir, TOKENIZER_DIR_NAME))

        _sync_model_version_to_s3(logger, shadow['run_id'], shadow_dir)

    logger.debug('Export complete')


# if __name__ == '__main__':
#     export_models()