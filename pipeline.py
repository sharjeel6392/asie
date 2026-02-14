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
from src.models.model_building import train_model
from src.utils.load_params import load_params
from src.utils.reproducibility import set_seed, capture_env
from src.serving.config import Settings


from constants import PARAMS_FILE, ARTIFACTS_DIR, ARTIFACTS_FILE, TOKENIZER_FILE

def hash_df(df: pd.DataFrame):
    return hashlib.md5(df.to_csv(index = False).encode()).hexdigest()

def get_git_hash():
    try:
        return subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode().strip()
    except Exception:
        return "not-a-git-repo"
    
def dataset_stats(df: pd.DataFrame) -> dict:
    return {
        'rows': len(df),
        'label_distribution': df['label'].value_counts().to_dict(),
        'avg_sentence_length': float(df['sentence'].str.len().mean()),
        'max_sentence_length': int(df['sentence'].str.len().max()),
    }

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

        mlflow.set_tracking_uri(Settings.MLFLOW_TRACKING_URI)
        print(f"Connected to MLflow at: {mlflow.get_tracking_uri()}")

        mlflow.set_experiment(cfg['experiment_name'])
        

        logging.info(f'Initiating data ingestion')
        df = ingest_data(cfg)
        stats = dataset_stats(df)
        data_hash = hash_df(df)
        logging.info(f'Data ingestion complete')

        # Data Preprocessing

        logging.info('Starting data preprocessing...')
        tokenizer = preprocess_data(cfg)
        logging.info('Data preprocessing completed and saved.')

        logging.info('Starting model training and mlflow logging...')

        set_seed(cfg['seed'])
        env_info = capture_env()
        git_hash = get_git_hash()
        # Model Training and Parameter logging with mlflow
        with mlflow.start_run() as run:
            print(f'RUN ID: {run.info.run_id}')

            model_temp_path, metrics = train_model(cfg)
            logging.info(f'Model training completed. Saving artifacts...')
            artifact_dict = {
                'metrics': metrics,
                'data_hash': data_hash,
                'data_stats': stats,
                'config': cfg,
                'env': env_info,
                'git_hash': git_hash,
            }

            if not os.path.exists(ARTIFACTS_DIR):
                os.makedirs(ARTIFACTS_DIR)
                print(f"Created directory: {ARTIFACTS_DIR}")
            
            file_path = os.path.join(ARTIFACTS_DIR, ARTIFACTS_FILE)
            if not os.path.exists(file_path):
                # This 'with open' in 'w' mode will create the file automatically 
                # as long as the directory exists.
                print(f"File {ARTIFACTS_FILE} does not exist. It will be created now.")


            with open(os.path.join(ARTIFACTS_DIR, ARTIFACTS_FILE), 'w') as f:
                json.dump(artifact_dict, f, indent = 2)
            mlflow.log_params(cfg)
            mlflow.log_params(env_info)
            mlflow.log_param('git_hash', git_hash)
            mlflow.log_metrics(metrics)
            mlflow.log_artifact(os.path.join(ARTIFACTS_DIR, ARTIFACTS_FILE))
            mlflow.log_artifacts(model_temp_path, artifact_path="model")
            
            tokenizer_file_path = os.path.join(ARTIFACTS_DIR, "tokenizer")
            tokenizer.save_pretrained(tokenizer_file_path)
            
            mlflow.log_artifacts(tokenizer_file_path, artifact_path=TOKENIZER_FILE)
            mlflow.log_dict(stats, 'data_stats.json')

            logging.info('Model and artifacts logged to mlflow successfully.')
            logging.info(f'Metrics: {metrics}')

            logging.info('Selecting and exporting the best performing model...') 
            '''
                Yet to add:
                    A method to pick the best performing model. (call src/models/promote model.py)
                    and then export the model and tokenizer artifacts from mlflow to local ./export_model by calling src/models/export_model.py
            '''
    except Exception as e:
        logging.error(f'Pipeline failed with error: {e}')
        raise

def run_sweep(sweep_params):
    for params in sweep_params:
        run_pipeline(params)

if __name__ == '__main__':
    # args = parse_args()

    # overrides = {
    #     'lr': args.lr,
    #     'batch_size': args.batch_size,
    #     'epochs': args.epochs,
    #     'max_length': args. max_length,
    # }
    
    # run_pipeline(overrides)

    sweep = [
        {'lr': 2e-5, 'epochs': 5, 'seed': 123},     # primary model
        {'lr': 2e-4, 'epochs': 5},                  # shadow model
    ]

    run_sweep(sweep)
    