import os
import json
import mlflow
import hashlib
import pandas as pd

from logger import logging
from data_manipulation.data_ingestion import ingest_data
from data_manipulation.data_preprocessing import preprocess_data, save_data as save_preprocessed_data
from model.model_building import train_model, load_data as load_data_for_model
from utils.load_params import load_params

from sklearn.model_selection import train_test_split

from constants import PARAMS_FILE, ARTIFACTS_DIR, ARTIFACTS_FILE

def hash_df(df: pd.DataFrame):
    return hashlib.md5(df.to_csv(index = False).encode()).hexdigest()


def run_pipeline():
    try:
        cfg = load_params(PARAMS_FILE)

        os.makedirs(ARTIFACTS_DIR, exist_ok= True)
        mlflow.set_experiment(cfg['experiment_name'])

        logging.info(f'Initiating data ingestion')
        df = ingest_data()
        data_hash = hash_df(df)
        logging.info(f'Data ingestion complete')

        # Data Preprocessing

        logging.info('Starting data preprocessing...')
        preprocess_data()
        logging.info('Data preprocessing completed and saved.')

        logging.info('Starting model training and mlflow logging...')
        # Model Training and Parameter logging with mlflow
        with mlflow.start_run():

            model_temp_path, metrics = train_model()
            logging.info(f'Model training completed. Saving artifacts...')
            artifact_dict = {
                'metrics': metrics,
                'data_hash': data_hash,
                'config': cfg,
            }

            with open(os.path.join(ARTIFACTS_DIR, ARTIFACTS_FILE), 'w') as f:
                json.dump(artifact_dict, f, indent = 2)
            mlflow.log_params(cfg)
            mlflow.log_metrics(metrics)
            mlflow.log_artifact(os.path.join(ARTIFACTS_DIR, ARTIFACTS_FILE))
            mlflow.log_artifacts(model_temp_path, artifact_path="model")

            logging.info('Model and artifacts logged to mlflow successfully.')
            logging.info(f'Metrics: {metrics}')
    except Exception as e:
        logging.error(f'Pipeline failed with error: {e}')
        raise


if __name__ == '__main__':
    run_pipeline()