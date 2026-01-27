#from src.logger import logging
import logging
from datasets import load_dataset
from sklearn.model_selection import train_test_split
import os
import pandas as pd
import yaml

def load_params(param_path: str) -> dict:
    """
        Load parameters from a YAML file
    """
    try:
        with open(param_path, 'r') as file:
            params = yaml.safe_load(file)

        base = params['artifact_dir']
        params['model_dir'] = params['model_dir'].replace('${artifact_dir}', base)
        params['logging_dir'] = params['logging_dir'].replace('${artifact_dir}', base)
        
        logging.debug(f'Parameters retrieved from {param_path}')
        return params
    except FileNotFoundError as e:
        logging.error(f'Parameter file not found: {e}')
        raise
    except yaml.YAMLError as e:
        logging.error(f'Error parsing YAML file: {e}')
        raise
    except Exception as e:
        logging.error(f'Unexpected error occurred while loading parameters: {e}')
        raise

def load_data(data_url: str) -> pd.DataFrame:
    """
        Load data from Hugging Face
    """
    try:
        df = pd.read_csv(data_url)
        logging.info(f'Data loaded from {data_url} successfully')
        return df
    except pd.errors.ParserError as e:
        logging.error(f'Failed to parse CSV file from {data_url}: {e}')
        raise
    except Exception as e:
        logging.error(f'Unexpected error occurred while loading the data: {e}')
        raise

def save_data(train_data: pd.DataFrame, val_data: pd.DataFrame, data_path: str) -> None:
    """
        Split the data into train and test set and save them separately
    """
    try:
        raw_data_path = os.path.join(data_path, 'raw')
        os.makedirs(raw_data_path, exist_ok= True)
        train_data.to_csv(os.path.join(raw_data_path, 'train_data.csv'), index= False)
        val_data.to_csv(os.path.join(raw_data_path, 'val_data.csv'), index= False)
        logging.debug(f'Train and Validation data saved to {raw_data_path}')
    except Exception as e:
        logging.error(f'Unexpected error while saving the data: {e}')
        raise


def main():
    try:
        params = load_params(param_path='./configs/train.yaml')
        test_size = params['test_size']
        df = load_data(data_url='./data/financial_phrasebank.csv')
        print(f'df head: {df.head()}')
        if df is None or df.empty:
            logging.error('Loaded dataframe is empty or None. Aborting data ingestion process.')
            raise ValueError('Loaded dataframe is empty or None.')
        train_df, val_df = train_test_split(df, test_size=test_size, random_state=42)
        save_data(train_df, val_df, data_path = './data/')

    except Exception as e:
        logging.error(f'Failed to complete the data ingestion process: {e}')
        raise

if __name__ == '__main__':
    main()