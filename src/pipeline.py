import os
import json
import mlflow
import hashlib
import pandas as pd
import subprocess
import argparse

from src.logger import logging
from src.data_manipulation.data_ingestion import ingest_data
from src.data_manipulation.data_preprocessing import preprocess_data
from src.model.model_building import train_model
from src.utils.load_params import load_params
from src.utils.reproducibility import set_seed, capture_env


from constants import PARAMS_FILE, ARTIFACTS_DIR, ARTIFACTS_FILE

def hash_df(df: pd.DataFrame):
    return hashlib.md5(df.to_csv(index = False).encode()).hexdigest()

def get_git_hash():
    try:
        return subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode().strip()
    except Exception:
        return "not-a-git-repo"

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=PARAMS_FILE)
    parser.add_argument('--lr', type=float)
    parser.add_argument('--batch_size', type=int)
    parser.add_argument('--epochs', type=int)
    parser.add_argument('--max_length', type=int)
    return parser.parse_args()


def run_pipeline(overrides = None):
    try:
        cfg = load_params(PARAMS_FILE)

        if overrides:
            for k, v in overrides.items():
                if v is not None:
                    cfg[k] = v

        os.makedirs(ARTIFACTS_DIR, exist_ok= True)
        mlflow.set_experiment(cfg['experiment_name'])

        logging.info(f'Initiating data ingestion')
        df = ingest_data(cfg)
        data_hash = hash_df(df)
        logging.info(f'Data ingestion complete')

        # Data Preprocessing

        logging.info('Starting data preprocessing...')
        preprocess_data(cfg)
        logging.info('Data preprocessing completed and saved.')

        logging.info('Starting model training and mlflow logging...')

        set_seed(cfg['seed'])
        env_info = capture_env()
        git_hash = get_git_hash()
        # Model Training and Parameter logging with mlflow
        with mlflow.start_run():

            model_temp_path, metrics = train_model(cfg)
            logging.info(f'Model training completed. Saving artifacts...')
            artifact_dict = {
                'metrics': metrics,
                'data_hash': data_hash,
                'config': cfg,
                'env': env_info,
                'git_hash': git_hash,
            }

            with open(os.path.join(ARTIFACTS_DIR, ARTIFACTS_FILE), 'w') as f:
                json.dump(artifact_dict, f, indent = 2)
            mlflow.log_params(cfg)
            mlflow.log_params(env_info)
            mlflow.log_param('git_hash', git_hash)
            mlflow.log_metrics(metrics)
            mlflow.log_artifact(os.path.join(ARTIFACTS_DIR, ARTIFACTS_FILE))
            mlflow.log_artifacts(model_temp_path, artifact_path="model")

            logging.info('Model and artifacts logged to mlflow successfully.')
            logging.info(f'Metrics: {metrics}')
    except Exception as e:
        logging.error(f'Pipeline failed with error: {e}')
        raise


if __name__ == '__main__':
    args = parse_args()

    overrides = {
        'lr': args.lr,
        'batch_size': args.batch_size,
        'epochs': args.epochs,
        'max_length': args. max_length,
    }
    
    run_pipeline(overrides)