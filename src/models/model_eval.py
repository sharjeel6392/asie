from sklearn.metrics import f1_score
import numpy as np

def compute_metrics(eval_pred):
    # 1. Properly unpack the named tuple
    logits, labels = eval_pred
    
    # 2. Safety check: Handle tuple outputs (the fix for your previous error!)
    if isinstance(logits, tuple):
        logits = logits[0]
        
    # 3. Calculate predictions
    # Use np.argmax because logits from the Trainer are usually NumPy arrays
    preds = np.argmax(logits, axis=-1)
    
    # 4. Return clean, serialized types (floats) for MLflow/Logging
    return {
        'f1': float(f1_score(labels, preds, average='weighted'))
    }