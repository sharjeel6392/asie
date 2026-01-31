import logging
from sklearn.model_selection import train_test_split
import pandas as pd
from utils.load_params import load_params
from utils.load_data import load_data
from utils.save_data import save_data
from constants import TRUE_DATA_FILE, PARAMS_FILE, RAW_DATA_DIR

def ingest_data() -> pd.DataFrame:
    """
    Docstring for ingest_data
    
    :param data_url: Path to the data file
    :type data_url: str
    :return: None
    """
    try:
        cfg = load_params(params_path=PARAMS_FILE)
        logging.debug('Ingesting data...')
        df = load_data(data_path=TRUE_DATA_FILE)
        train_df, val_df = train_test_split(df, test_size= cfg['test_size'], random_state = cfg['seed'])
        logging.debug('Data ingestion completed.')
        save_data(train_df, val_df, data_path=RAW_DATA_DIR)
        logging.info(f'Train and validation data saved to {RAW_DATA_DIR}')
        return df
    except Exception as e:
        logging.error(f'Failed to complete the data ingestion process: {e}')
        raise




def main():
    ingest_data()

if __name__ == '__main__':
    main()