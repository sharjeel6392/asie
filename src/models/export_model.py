import os
import shutil
import mlflow
from mlflow import tracking
from mlflow import artifacts

from models.model_resolver import get_promoted_model
from serving.config import Settings

EXPORT_DIR = "exported_model"

def export():
    model = get_promoted_model()
    print(model)

    mlflow.set_tracking_uri(Settings.MLFLOW_TRACKING_URI)
    print(tracking.get_tracking_uri)

    model_uri = f'runs:/{model['run_id']}/model'
    tokenizer_uri = f'runs:/{model['run_id']}/tokenizer'

    print(f'Model_URI: {model_uri}\nTokenizer URI: {tokenizer_uri}')

    print('Downloading model...')
    model_path = artifacts.download_artifacts(model_uri)

    print('Downloading tokenizer...')
    tokenizer_path = artifacts.download_artifacts(tokenizer_uri)

    if os.path.exists(EXPORT_DIR):
        shutil.rmtree(EXPORT_DIR)

    os.makedirs(EXPORT_DIR)

    shutil.copytree(model_path, os.path.join(EXPORT_DIR, "model"))
    shutil.copytree(tokenizer_path, os.path.join(EXPORT_DIR, "tokenizer"))

    print('Export complete')


if __name__ == '__main__':
    export()