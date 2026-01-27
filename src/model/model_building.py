import os
import pandas as pd
import logging
import pickle
from constants import MODEL_DIR, MODEL_FILE
from datasets import Dataset, load_dataset
import torch
from transformers import AutoModelForSequenceClassification, Trainer, TrainingArguments
import yaml
from model.model_eval import compute_metrics

def load_params(params_path: str) -> dict:
    """
        Load parameters from a YAML file.
    """
    try:
        with open(params_path, 'r') as file:
            params = yaml.safe_load(file)
        logging.debug(f'Parameters retrieved from {params_path}')
        return params
    except FileNotFoundError:
        logging.error(f'File not found {params_path}')
        raise
    except yaml.YAMLError as e:
        logging.error(f'YAML error: {e}')
        raise
    except Exception as e:
        logging.error(f'Unexpected error: {e}')
        raise

def load_data(file_path: str):
    try:
        ds = load_dataset('parquet', data_files= file_path, split = 'train')
        if isinstance(ds, Dataset):
            column_names = ds.column_names
            if column_names and 'label' in column_names:
                ds = ds.rename_column('label', 'labels')
            ds.set_format(type = 'torch', columns=['input_ids', 'attention_mask', 'labels'])
        else:
            if 'label' in next(iter(ds)): # Peek at first row for columns
                ds = ds.rename_column('label', 'labels')
            ds = ds.with_format('torch')
        return ds
    except pd.errors.ParserError as e:
        logging.error(f'Failed to parse the parquet file: {e}')
        raise
    except Exception as e:
        logging.error(f'Unexpected error occured while loading the data for model building: {e}')
        raise

def train_model(train_ds, val_ds, cfg: dict):
    try:
        model = AutoModelForSequenceClassification.from_pretrained(cfg['model_name'], num_labels = 3)
        device_is_gpu = torch.cuda.is_available()
        args = TrainingArguments(
            output_dir = './runs',
            fp16= device_is_gpu,
            per_device_train_batch_size= int(cfg['batch_size']),
            num_train_epochs = int(cfg['epochs']),
            learning_rate= float(cfg['lr']),
            eval_strategy='epoch',
            logging_steps=50,
            report_to='none',
        )

        trainer = Trainer(
            model = model,
            args = args,
            train_dataset= train_ds,
            eval_dataset =val_ds,
            compute_metrics= compute_metrics,
        )
        trainer.train()
        metrics = trainer.evaluate()
        save_path = os.path.join(cfg['model_dir'], 'temp_model_artifacts')
        os.makedirs(save_path, exist_ok = True)
        trainer.save_model(save_path)
        return save_path, metrics
    except Exception as e:
        logging.error(f'Unexpected error occured during model training: {e}')
        raise

def save_model(model: AutoModelForSequenceClassification, file_path: str) -> None:
    try:
        with open(file_path, 'wb') as file:
            pickle.dump(model, file)
        logging.info(f'Model saved to {file_path}')
    except Exception as e:
        logging.error(f'Unexpected error occured while saving the model: {e}')
        raise

def main():
    print(f'Pytorch version: {torch.__version__}')
    print(f'CUDA available: {torch.cuda.is_available()}')
    print(f'Device name: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"}')

    try:
        cfg = load_params('./configs/train.yaml')
        train_ds = load_data('./data/preprocessed/train_data.parquet')
        val_ds = load_data('./data/preprocessed/val_data.parquet')

        metrics = train_model(train_ds, val_ds, cfg)
        os.makedirs(MODEL_DIR, exist_ok=True)
        model_file_path = os.path.join(MODEL_DIR, MODEL_FILE)

        # save_model(clf, model_file_path)
    except Exception as e:
        logging.error(f'Failed to complete the model building process: {e}')
    
if __name__ == '__main__':
    main()