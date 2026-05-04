import random
import numpy as np
import torch
import platform
import transformers

def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)

def capture_env() -> dict:
    return {
        'python_version': platform.python_version(),
        'os': platform.platform(),
        'torch_version': torch.__version__,
        'transformer_version': transformers.__version__,
        'cuda_available': torch.cuda.is_available(),
    }