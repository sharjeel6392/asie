MODEL_DIR = './models'
MODEL_FILE = 'model.pkl'

DATA_DIR = './data'
RAW_DATA_DIR = f'{DATA_DIR}/raw'
PREPROCESSED_DATA_DIR = f'{DATA_DIR}/preprocessed'

TRAIN_DATA_FILE = 'train_data.parquet'
VAL_DATA_FILE = 'val_data.parquet'
TRUE_DATA_FILE = f'{DATA_DIR}/financial_phrasebank.parquet'

PARAMS_FILE = './configs/train.yaml'
LOGS_DIR = './logs'

ARTIFACTS_DIR = './artifacts'
ARTIFACTS_FILE = 'run_artifacts.json'

MODEL_DIR = './model'
MODEL_FILE = f'{MODEL_DIR}/model_artifact'
TOKENIZER_FILE = 'tokenizer'

REGISTRY_PATH = './model/model_registry.yaml'

MLRUNS_DIR = './mlruns'

EXPERIMENT_NAME = 'ASIE_Week1'

MAX_BATCH_SIZE = 32