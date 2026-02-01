import os
import torch
from datasets import Dataset
from transformers import AutoModelForSequenceClassification, Trainer, TrainingArguments

from src.logger import logging
from src.models.model_eval import compute_metrics
from src.utils.load_data import load_data
from src.constants import PREPROCESSED_DATA_DIR, TRAIN_DATA_FILE, VAL_DATA_FILE, MODEL_DIR, MODEL_FILE

def train_model(cfg: dict) -> tuple[str, dict[str, float]]:
    try:
        logging.debug("Initiating model building")
        train_ds = Dataset.from_pandas(load_data(os.path.join(PREPROCESSED_DATA_DIR, TRAIN_DATA_FILE)))
        if train_ds is None:
            logging.error('Loaded test dataframe is None. Aborting preprocessing.')
            raise ValueError('Loaded train dataframe is None.')
        
        val_ds = Dataset.from_pandas(load_data(os.path.join(PREPROCESSED_DATA_DIR, VAL_DATA_FILE)))
        if val_ds is None:
            logging.error('Loaded validation dataframe is None. Aborting preprocessing.')
            raise ValueError('Loaded validation dataframe is None.')

        model = AutoModelForSequenceClassification.from_pretrained(cfg['model_name'], num_labels = 3)
        device_is_gpu = torch.cuda.is_available()
        logging.debug("Training started")
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
        logging.debug("Training completed")
        metrics = trainer.evaluate()
        save_path = os.path.join(MODEL_DIR, MODEL_FILE)
        os.makedirs(save_path, exist_ok = True)
        trainer.save_model(save_path)
        logging.debug(f"Model saved at {save_path}")
        return save_path, metrics
    except Exception as e:
        logging.error(f'Unexpected error occured during model training: {e}')
        raise