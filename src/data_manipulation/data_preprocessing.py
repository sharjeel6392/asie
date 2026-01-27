import logging
from transformers import AutoTokenizer
from sklearn.model_selection import train_test_split
import os
import pandas as pd
import yaml
from datasets import Dataset

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

def load_data(data_path: str):
    """
        Load data from a csv file
    """
    try:
        df = pd.read_csv(data_path)
        logging.info(f'Data loaded from {data_path}')
        return df
    except pd.errors.ParserError as e:
        logging.error(f'Failed to parse the CSV file: {e}')
        raise
    except Exception as e:
        logging.error(f'Unexpected error occurred while loading the data: {e}')
        raise

def preprocess_data(train_df: pd.DataFrame, val_df:pd.DataFrame, model_name: str, max_length: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
        Preprocess the data
    """
    try:
        print("INSIDE PREPROCESS")
        print(f'train_df head before preprocessing: \n {train_df.head()}')
        print(f'val_df head before preprocessing: \n {val_df.head()}')
        print(f'Model Name: {model_name}, Max length: {max_length}')
        logging.info('Pre-processing...')
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        def tokenize_row(row):
            return tokenizer(
            row['sentence'],
            padding = 'max_length',
            truncation = True,
            max_length = max_length,
        )

        train_df['tokenized'] = train_df.apply(tokenize_row, axis = 1)
        val_df['tokenized'] = val_df.apply(tokenize_row, axis=1)

        train_tokenized = pd.DataFrame(train_df['tokenized'].tolist())
        val_tokenized = pd.DataFrame(val_df['tokenized'].tolist())

        train_df = pd.concat([train_df.drop(columns=['tokenized','sentence']), train_tokenized], axis = 1)
        val_df = pd.concat([val_df.drop(columns=['tokenized','sentence']), val_tokenized], axis = 1)

        train_df.rename(columns={'labels': 'label'})
        val_df.rename(columns={'labels': 'label'})

        logging.info('Pre-processing completed.')
        return train_df, val_df
        
    except Exception as e:
        logging.error(f'Unexpected error occured while preprocessing: {e}')
        raise

def save_data(train_data: pd.DataFrame, val_data: pd.DataFrame, data_path: str) -> None:
    """
        Split the data into train and test set and save them separately
    """
    try:
        raw_data_path = os.path.join(data_path, 'preprocessed')
        os.makedirs(raw_data_path, exist_ok= True)
        train_data.to_parquet(os.path.join(raw_data_path, 'train_data.parquet'), index= False)
        val_data.to_parquet(os.path.join(raw_data_path, 'val_data.parquet'), index= False)
        logging.debug(f'Train and Validation data saved to {raw_data_path}')
    except Exception as e:
        logging.error(f'Unexpected error while saving the data: {e}')
        raise

def main():
    try:
        params = load_params(params_path = './configs/train.yaml')
        model_name = params['model_name']
        max_length = params['max_length']
        train_df = load_data(data_path = './data/raw/train_data.csv')
        val_df = load_data(data_path='./data/raw/val_data.csv')

        if train_df is None:
            logging.error('Loaded test dataframe is None. Aborting preprocessing.')
            raise ValueError('Loaded train dataframe is None.')
        if val_df is None:
            logging.error('Loaded validation dataframe is None. Aborting preprocessing.')
            raise ValueError('Loaded validation dataframe is None.')
        train_df_preprocessed, val_df_preprocessed = preprocess_data(train_df, val_df, model_name, max_length)
        save_data(train_df_preprocessed, val_df_preprocessed, data_path='./data/')
        logging.debug('Preprocessed data saved to {data_path}/preprocessed')
    except Exception as e:
        logging.error(f'Failed to complete the data ingestion process: {e}')
        raise

if __name__ == '__main__':
    main()