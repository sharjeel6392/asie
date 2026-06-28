import yaml
from src.logger import configure_logger

def load_params(params_path: str) -> dict:
    """
        Load parameters from a YAML file.
    """
    logger = configure_logger()
    try:
        with open(params_path, 'r') as file:
            params = yaml.safe_load(file)
        logger.debug(f'Parameters retrieved from {params_path}')
        return params
    except FileNotFoundError:
        logger.error(f'File not found {params_path}')
        raise
    except yaml.YAMLError as e:
        logger.error(f'YAML error: {e}')
        raise
    except Exception as e:
        logger.error(f'Unexpected error: {e}')
        raise