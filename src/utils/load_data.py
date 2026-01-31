import pandas as pd
import logging
def load_data(data_path: str):
    """
        Load data from a csv file
    """
    try:
        df = pd.read_parquet(data_path)
        logging.info(f'Data loaded from {data_path}')
        return df
    except pd.errors.ParserError as e:
        logging.error(f'Failed to parse the parquet file: {e}')
        raise
    except Exception as e:
        logging.error(f'Unexpected error occurred while loading the data: {e}')
        raise