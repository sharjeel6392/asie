from sklearn.model_selection import train_test_split
import pandas as pd

from src.logger import logging
from src.utils.load_data import load_data
from src.utils.save_data import save_data
from src.constants import TRUE_DATA_FILE, RAW_DATA_DIR

REQUIRED_COLUMNS = ['sentence', 'label']

def ingest_data(cfg: dict) -> pd.DataFrame:
    """
    Docstring for ingest_data
    
    :param data_url: Path to the data file
    :type data_url: str
    :return: None
    """
    try:
        logging.debug('Ingesting data...')
        df = load_data(data_path=TRUE_DATA_FILE)
        
        for col in REQUIRED_COLUMNS:
            if col not in df.columns:
                raise ValueError(f'Missing required column: {col}')
        
        if df['sentence'].isnull().any():
            raise ValueError('Null values found in sentence column')
        
        if df['label'].isnull().any():
            raise ValueError('Null values found in label column')
        
        if not df['label'].between(0, 2).all():
            raise ValueError('Labels must be in range [0, 2]')

        train_df, val_df = train_test_split(df, test_size= cfg['test_size'], random_state = cfg['seed'])
        logging.debug('Data ingestion completed.')
        save_data(train_df, val_df, data_path=RAW_DATA_DIR)
        logging.info(f'Train and validation data saved to {RAW_DATA_DIR}')
        return df
    except Exception as e:
        logging.error(f'Failed to complete the data ingestion process: {e}')
        raise