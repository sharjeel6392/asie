import os
import torch
from datasets import Dataset
from transformers import AutoModelForSequenceClassification, Trainer, TrainingArguments

from src.logger import configure_logger
from src.models.model_eval import compute_metrics
from src.utils.load_data import load_data
from src.constants import PREPROCESSED_DATA_DIR, TRAIN_DATA_FILE, VAL_DATA_FILE, MODEL_DIR, MODEL_FILE

os.environ["TOKENIZERS_PARALLELISM"] = "false"

class HFTransformerModel:
    """
    HuggingFace Transformer-based model for classification tasks.
    This class encapsulates the training, evaluation, and saving/loading
    of a transformer model for plug-and-play usage in the ASIE pipeline.
    """
    def __init__(self, model_name: str, num_labels: int = 3):
        self.model_name = model_name
        self.num_labels = num_labels
        self.model = None
        self.tokenizer = None
    
    def train(self, cfg: dict) -> dict:
        """
        Train the mode using HuggingFace's Trainer API.

        Args:
            cfg (dict): Training Configuration

        Returns:
            dict: Evaluation metrics after training
        """
        logger = configure_logger()
        try:
            logger.debug("Loading dataset")

            train_df = load_data(os.path.join(PREPROCESSED_DATA_DIR, TRAIN_DATA_FILE))
            if train_df is None:
                raise ValueError('Train dataset is None.')
            
            val_df = load_data(os.path.join(PREPROCESSED_DATA_DIR, VAL_DATA_FILE))
            if val_df is None:
                raise ValueError('Loaded validation dataset is None.')
            
            train_ds = Dataset.from_pandas(train_df)
            val_ds = Dataset.from_pandas(val_df)

            logger.debug("Initializing model")
            self.model = AutoModelForSequenceClassification.from_pretrained(
                self.model_name, num_labels=self.num_labels
            )

            device_is_gpu = torch.cuda.is_available()
            logger.debug("Starting training")

            training_args = TrainingArguments(
                output_dir = os.path.abspath("./runs"),
                save_total_limit=1,
                fp16=device_is_gpu,
                per_device_train_batch_size=int(cfg['batch_size']),
                num_train_epochs=int(cfg['epochs']),
                learning_rate=float(cfg['lr']),

                # ✅ FIXES FOR AIRFLOW
                dataloader_num_workers=0,
                disable_tqdm=True,

                # ✅ Logging (cleaner + safer)
                logging_strategy="steps",
                logging_steps=50,

                # ✅ Eval
                eval_strategy="epoch",

                # ✅ Disable external integrations
                report_to="none",
            )

            trainer = Trainer(
                model = self.model,
                args = training_args,
                train_dataset= train_ds,
                eval_dataset= val_ds,
                compute_metrics= compute_metrics,
            )

            logger.debug("Training in progress...")
            trainer.train()

            logger.debug("Training completed. Evaluating model...")
            metrics = trainer.evaluate()

            self.trainer = trainer
            return metrics
        
        except Exception as e:
            logger.error(f"Training failed: {e}")
            raise

    def save(self) -> str:
        """
        save trained model to disk.
        Returns:
            str: Path where the model is saved.
        """
        logger = configure_logger()
        save_path = os.path.join(MODEL_DIR, MODEL_FILE)
        os.makedirs(save_path, exist_ok=True)

        self.trainer.save_model(save_path)

        logger.debug(f'Model saved at {save_path}')
        return save_path