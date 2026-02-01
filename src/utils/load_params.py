import yaml
import logging
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