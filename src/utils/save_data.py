import pandas as pd
import os

from src.logger import configure_logger
from src.constants import TRAIN_DATA_FILE, VAL_DATA_FILE

def save_data(train_data: pd.DataFrame, val_data: pd.DataFrame, data_path: str) -> None:
    """
        Split the data into train and test set and save them separately
    """
    logger = configure_logger()
    try:
        os.makedirs(data_path, exist_ok= True)
        train_data.to_parquet(os.path.join(data_path, TRAIN_DATA_FILE), index= False)
        val_data.to_parquet(os.path.join(data_path, VAL_DATA_FILE), index= False)
        logger.debug(f'Train and Validation data saved to {data_path}')
    except Exception as e:
        logger.error(f'Unexpected error while saving the data: {e}')
        raise