from transformers import AutoModelForSequenceClassification
import pickle
import logging
def save_model(model: AutoModelForSequenceClassification, file_path: str) -> None:
    try:
        with open(file_path, 'wb') as file:
            pickle.dump(model, file)
        logging.info(f'Model saved to {file_path}')
    except Exception as e:
        logging.error(f'Unexpected error occured while saving the model: {e}')
        raise