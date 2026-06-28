from src.models.factory import get_model
from src.logger import configure_logger


def train_model(cfg: dict) -> tuple[str, dict]:
    """
    Wrapper around model abstraction layer
    to train a model and return its type and evaluation metrics
    Args:
        cfg (dict): Configuration dictionary for model training

    Returns:
        tuple[str, dict]: Path to the saved model and evaluation metrics
    """
    logger = configure_logger()
    try:
        logger.debug("Initializing model building")

        model = get_model(cfg)

        metrics = model.train(cfg)
        save_path = model.save()

        return save_path, metrics
    
    except Exception as e:
        logger.error(f'Unexpected error during model training: {e}')
        raise