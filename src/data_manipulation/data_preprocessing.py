import logging
from transformers import AutoTokenizer
import pandas as pd
from utils.load_data import load_data
from utils.save_data import save_data
from constants import PREPROCESSED_DATA_DIR, TRAIN_DATA_FILE, VAL_DATA_FILE, PARAMS_FILE, RAW_DATA_DIR, MODEL_DIR
from utils.load_params import load_params
import os


def preprocess_data() -> None:
    """
        Preprocess the data
    """
    try:
        logging.debug('Pre-processing...')

        params = load_params(params_path=PARAMS_FILE)
        model_name = params['model_name']
        max_length = params['max_length']

        train_df = load_data(data_path=os.path.join(RAW_DATA_DIR, TRAIN_DATA_FILE))
        if train_df is None:
            logging.error('Loaded test dataframe is None. Aborting preprocessing.')
            raise ValueError('Loaded train dataframe is Empty.')

        val_df = load_data(data_path = os.path.join(RAW_DATA_DIR, VAL_DATA_FILE))
        if val_df is None:
            logging.error('Loaded validation dataframe is None. Aborting preprocessing.')
            raise ValueError('Loaded validation dataframe is None.')

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

        logging.debug('Pre-processing completed.')

        save_data(train_df, val_df, PREPROCESSED_DATA_DIR)
        
    except Exception as e:
        logging.error(f'Unexpected error occured while preprocessing: {e}')
        raise

def main():
    preprocess_data()

if __name__ == '__main__':
    main()