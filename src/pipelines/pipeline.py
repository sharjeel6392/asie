import os
import json
import mlflow
import hashlib
import pandas as pd
import subprocess
import argparse
import datetime

from src.logger import logging
from src.data_manipulation.data_ingestion import ingest_data
from src.data_manipulation.data_preprocessing import preprocess_data
from src.models.model_building import train_model
from src.utils.load_params import load_params
from src.utils.reproducibility import set_seed, capture_env
from src.serving.config import Settings
from src.models.model_eval import evaluate_model
from src.experiments.schemas import ExperimentResult


from src.constants import PARAMS_FILE, ARTIFACTS_DIR, ARTIFACTS_FILE, TOKENIZER_FILE

def hash_df(df: pd.DataFrame) -> str:
    """
    Generate a determinstic hash for a dataframe.

    This is used to track dataset versions across pipeline runs and
    ensure resproducibility by identifying whether the input data has changed.

    Args:
        df (pd.DataFrame): Input dataset as a pandas DataFrame.

    Returns:
        str: MD5 hash representing the dataset content.
    """
    return hashlib.md5(df.to_csv(index = False).encode()).hexdigest()

def get_git_hash() -> str:
    """
    Retrieve the current Git commit hash of the repository.

    This enables tracebility between model artifacts and the exact code version
    used during training.

    Returns:
        str: Git commit hash, or "not-a-git-repo" if unavailable.
    """
    try:
        return subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode().strip()
    except Exception:
        return "not-a-git-repo"
    
def dataset_stats(df: pd.DataFrame) -> dict:
    """
    Compute basic descriptive statistics for the dataset.

    These statistics are logged as artifacts for monitoring
    and debugging data-related issues in the pipeline.

    Args:
        df (pd.DataFrame): Input dataset as a pandas DataFrame.
    
    Returns:
        dict: Summary statistics including number of rows, label distribution,
                average sentence length, and maximum sentence length.
    """
    
    return {
        'rows': len(df),
        'label_distribution': df['label'].value_counts().to_dict(),
        'avg_sentence_length': float(df['sentence'].str.len().mean()),
        'max_sentence_length': int(df['sentence'].str.len().max()),
    }

def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments for pipeline execution.

    Allows overriding default configuration parameters such as
    learning rate, batch size, number of epocks and max sequence length.

    Returns:
        argparse.Namespace: Parsed command-line arguments with
        attributes corresponding to each parameter.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=PARAMS_FILE)
    parser.add_argument('--lr', type=float)
    parser.add_argument('--batch_size', type=int)
    parser.add_argument('--epochs', type=int)
    parser.add_argument('--max_length', type=int)
    return parser.parse_args()

def normalize_metrics(metrics: dict) -> dict:
    """
    Normalize and standardize model evaluation metrics for consistent logging.

    Ensures consistent metric keys and fallback values to prevent
    downstream failures during model comparison and selection.

    Args:
        metrics (dict): Raw metrics returned from training.

    Returns:
        dict: Normalized metrics with standardized keys and default values.
    """
    return {
        "eval_f1": metrics.get("eval_f1", 0),
        "eval_loss": metrics.get("eval_loss", float('inf'))
    }

def _prepare_data(cfg) -> tuple[pd.DataFrame, dict, str]:
    df = ingest_data(cfg)
    stats = dataset_stats(df)
    data_hash = hash_df(df)
    return df, stats, data_hash

def _setup_mlflow(cfg) -> None:
    mlflow.set_tracking_uri(Settings.MLFLOW_TRACKING_URI)
    mlflow.set_experiment(cfg['experiment_name'])

def run_pipeline(overrides: dict | None = None) -> ExperimentResult:
    """
    Execute the end-to-end training pipeline.

    This function orchestrates data ingestion, preprocessing, model training, 
    and artifact logging using MLflow. It returns a structured result that
    can be consumed by orchestration systems for model selection and promotion.

    Workflow:
    1. Load and override configuration parameters.
    2. Set up MLflow tracking.
    3. Ingest and preprocess data, computing dataset statistics and hash.
    4. Train model and evaluate metrics.
    5. Log parameters, metrics, and artifacts to MLflow.
    6. Return a structured result with run ID, metrics, config, data hash, and status.

    Args:
        overrides (dict, optional): Configuration parameters to override defaults.
    
    Returns:
        dict: Structured pipeline output containing:
            - run_id (str): MLflow run ID for traceability.
            - metrics (dict): Evaluation metrics from model training.
            - config (dict): Final configuration used for the run.
            - data_hash (str): Dataset Identifier for reproducibility.
            - status (str): "success" or "failure" indicating pipeline outcome.
            - timestamp (str): ISO formatted timestamp of pipeline execution.
            - error (str, optional): Error message if pipeline failed.
    """

    try:
        cfg = load_params(PARAMS_FILE)

        if overrides:
            for k, v in overrides.items():
                if v is not None:
                    cfg[k] = v

        _setup_mlflow(cfg)
        
        print(f"Connected to MLflow at: {mlflow.get_tracking_uri()}")

        logging.info(f'Initiating data ingestion')
        df, stats, data_hash = _prepare_data(cfg)
        logging.info(f'Data ingestion complete')
        
        # ===========================================================
        # Data Preprocessing
        # ===========================================================

        logging.info('Starting data preprocessing...')
        tokenizer = preprocess_data(cfg)
        logging.info('Data preprocessing completed and saved.')

        # ===========================================================
        # Training, Evaluation and MLflow Logging
        # ===========================================================
        logging.info('Starting model training and mlflow logging...')

        set_seed(cfg['seed'])
        env_info = capture_env()
        git_hash = get_git_hash()

        # ===========================================================
        # Model Training and Parameter logging with mlflow
        # ===========================================================
        with mlflow.start_run() as run:
            print(f'RUN ID: {run.info.run_id}')

            model_temp_path, metrics = train_model(cfg)
            metrics = normalize_metrics(metrics)
            evaluation = evaluate_model(metrics, threshold = 0.75)
            logging.info(f'Model training completed. Saving artifacts...')
            artifact_dict = {
                'metrics': metrics,
                'data_hash': data_hash,
                'data_stats': stats,
                'config': cfg,
                'env': env_info,
                'git_hash': git_hash,
            }

            if not os.path.exists(ARTIFACTS_DIR):
                os.makedirs(ARTIFACTS_DIR)
                print(f"Created directory: {ARTIFACTS_DIR}")
            
            file_path = os.path.join(ARTIFACTS_DIR, ARTIFACTS_FILE)
            if not os.path.exists(file_path):
                # This 'with open' in 'w' mode will create the file automatically 
                # as long as the directory exists.
                print(f"File {ARTIFACTS_FILE} does not exist. It will be created now.")


            with open(os.path.join(ARTIFACTS_DIR, ARTIFACTS_FILE), 'w') as f:
                json.dump(artifact_dict, f, indent = 2)

            tokenizer_file_path = os.path.join(ARTIFACTS_DIR, "tokenizer")
            tokenizer.save_pretrained(tokenizer_file_path)  # type: ignore

            mlflow.log_params(cfg)
            mlflow.log_params(env_info)
            mlflow.log_param('git_hash', git_hash)
            mlflow.log_metrics(metrics)
            mlflow.log_artifact(os.path.join(ARTIFACTS_DIR, ARTIFACTS_FILE))
            mlflow.log_artifacts(model_temp_path, artifact_path="model")            
            mlflow.log_artifacts(tokenizer_file_path, artifact_path=TOKENIZER_FILE)
            mlflow.log_dict(stats, 'data_stats.json')

            logging.info('Model and artifacts logged to mlflow successfully.')
            result: ExperimentResult = {
                "run_id": run.info.run_id,
                "metrics": metrics,
                "evaluation": evaluation,
                "config": cfg,
                "data_hash": data_hash,
                "status": "success",
                "timestamp": datetime.datetime.now().isoformat()
            }
            if not evaluation['passed']:
                result['status'] = 'failure'
                result['failure_reason'] = evaluation['reason']
        return result
    except Exception as e:
        logging.error(f'Pipeline failed with error: {e}')
        return {
            "run_id": None,
            "metrics": {},
            "evaluation": {"passed": False, "reason": "pipeline exception"},
            "config": overrides if overrides else {},
            "status": "failure",
            "error": str(e),
            "timestamp": datetime.datetime.now().isoformat()
        }


def run_experiments(sweep_params: list[dict]) -> list[ExperimentResult]:
    """
    Execute multiple pipeline runs with different hyperparameter configurations.
    
    This function is used for hyperparameter tuning and model comparison by running the 
    pipeline with various parameter combinations defined in the sweep_params list.

    Args:
        sweep_params (list[dict]): List of parameter dictionaries.

    Returns:
        list[dict]: list of structured pipeline results.
    """
    return [run_pipeline(params) for params in sweep_params]

if __name__ == '__main__':
    # parser = argparse.ArgumentParser()
    # parser.add_argument("--lr", type=float)
    # parser.add_argument("--epochs", type=int)

    # args = parser.parse_args()
    # overrides = {k: v for k, v in vars(args).items() if v is not None}

    # print(run_pipeline(overrides))

    sweep = [
        {'lr': 2e-5, 'epochs': 5, 'seed': 123},     # primary model
        {'lr': 2e-4, 'epochs': 5},                  # shadow model
    ]

    print(run_experiments(sweep))
    