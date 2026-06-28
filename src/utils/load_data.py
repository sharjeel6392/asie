import pandas as pd
from src.logger import configure_logger

def load_data(data_path: str):
    """
        Load data from a csv file
    """
    logger = configure_logger()
    try:
        df = pd.read_parquet(data_path)
        
        if df.empty:
            raise ValueError('Dataset is empty')
        
        logger.info(f'Data loaded from {data_path}')
        return df
    
    except pd.errors.ParserError as e:
        logger.error(f'Failed to parse the parquet file: {e}')
        raise
    except Exception as e:
        logger.error(f'Unexpected error occurred while loading the data: {e}')
        raise