import torch
import yaml
import os
import json
import mlflow
from mlflow import pytorch as mlflow_pytorch
import hashlib
import pandas as pd
from datasets import Dataset

from logger import logging
from data.data_ingestion import load_data, save_data, load_params
from data.data_preprocessing import preprocess_data, save_data as save_preprocessed_data
from model.model_building import train_model, load_data as load_data_for_model

from sklearn.model_selection import train_test_split

def hash_df(df: pd.DataFrame):
    return hashlib.md5(df.to_csv(index = False).encode()).hexdigest()


def run_pipeline(cfg_path: str = './configs/train.yaml'):
    try:
        cfg = load_params(cfg_path)

        os.makedirs(cfg['artifact_dir'], exist_ok= True)
        mlflow.set_experiment(cfg['experiment_name'])
        
        logging.info('Starting data ingestion...')
        df = load_data(data_url='./data/financial_phrasebank.csv')
        test_size = cfg.get('test_size', 0.2)

        data_hash = hash_df(df)
        logging.info(f'Data hash: {data_hash}')
        logging.info('Data ingestion completed.')

        train_df, val_df = train_test_split(df, test_size= test_size, random_state = 42)
        save_data(train_df, val_df, data_path='./data/')
        logging.info('Data saved to raw directory.')

        # Data Preprocessing

        logging.info('Starting data preprocessing...')
        train_df, val_df = load_data(data_url='./data/raw/train_data.csv'), load_data(data_url = './data/raw/val_data.csv')
        train_enc, val_enc = preprocess_data(train_df, val_df, cfg['model_name'], cfg['max_length'])
        save_preprocessed_data(train_enc, val_enc, data_path = './data/')
        logging.info('Data preprocessing completed and saved.')
        logging.info('Starting model training and mlflow logging...')

        # Model Training and Parameter logging with mlflow
        train_ds, val_ds = load_data_for_model('./data/preprocessed/train_data.parquet'), load_data_for_model('./data/preprocessed/val_data.parquet')
        with mlflow.start_run():

            model_temp_path, metrics = train_model(train_ds, val_ds, cfg)
            logging.info(f'Model training completed. Saving artifacts...')
            artifact_dict = {
                'metrics': metrics,
                'data_hash': data_hash,
                'config': cfg,
            }

            with open(f'{cfg['artifact_dir']}/run_artifacts.json', 'w') as f:
                json.dump(artifact_dict, f, indent = 2)
            mlflow.log_params(cfg)
            mlflow.log_metrics(metrics)
            mlflow.log_artifact(f"{cfg['artifact_dir']}/run_artifacts.json")
            mlflow.log_artifacts(model_temp_path, artifact_path="model")

            logging.info('Model and artifacts logged to mlflow successfully.')
            logging.info(f'Metrics: {metrics}')
    except Exception as e:
        logging.error(f'Pipeline failed with error: {e}')
        raise


if __name__ == '__main__':
    run_pipeline()