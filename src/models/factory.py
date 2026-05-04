from src.models.hf_model import HFTransformerModel

def get_model(cfg: dict) -> HFTransformerModel:
    """
    Factory fucntion to instantiate and return the appropriate model based 
    on the configuration.

    This function abstracts away the underlying model type, allowing 
    the training pipeline and serving layer to remain agnostic to the
    specific model being used. It enables plug-and-play model swapping
    by simply changing the configuration, without requiring any code 
    changes.

    The factory inspects the 'model_type' field in the configuration
    and returns the corresponding model implementation.
    
    Supported model types:
        - 'transformer': HuggingFace-based transformer model for 
                         sequence classification tasks
    Args:
        cfg (dict): Configuration dictionary containing model parameters.
                    Expected keys include:
                        - 'model_type (str)': Type of model to instantiate
                        - 'model_name (str)': Pretrained model identifier
    
    Returns:
        HFTransformerModel: An instance of a model implementing the 
                            HFTransformerModel interface
    
    Raises:
        ValueError: If an unsupported model is provided.
    """
    model_type = cfg.get("model_type", "transformer")

    if model_type == "transformer":
        return HFTransformerModel(
            model_name= cfg['model_name'],
            num_labels= 3
        )
    
    raise ValueError(f'Unsupported model type: {model_type}')