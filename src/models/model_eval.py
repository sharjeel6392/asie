from sklearn.metrics import f1_score
import numpy as np


# =========================================================================
# Trainer-level metric computation function
# =========================================================================

def compute_metrics(eval_pred: tuple) -> dict:
    """
    Compute evaluation metrics for HuggingFace Trainer.
    This function is passed to the Trainer and is responsible
    for converting raw logits into meaningful metrics

    Args:
        eval_pred (tuple): A tuple containing (logits, labels)
                           from the evaluation dataset.
    Returns:
        dict: A dictionatyu containing the evaluation metrics
    """
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

# =========================================================================
# System-level evaluation 
# =========================================================================

def evaluate_model(metrics: dict, threshold: float = 0.75) -> dict:
    """
    Convert raw metrics into a decision signal.

    This function determines whether a trained model meets the
    minimum performance threshold required to proceed to the 
    next stage (e.g., shadow deployment)

    Args:
        metrics (dict): Output from model evaluation
        threshold (float): Minimum F1 score acceptable
    
    Returns: 
        dict: Evaluation result containing:
            - passed (bool): whether model meets the criteria
            - reason (str): Explanation of decision
            - score (float): F1 score used for evaluation
    """
    f1_score = float(metrics.get('eval_f1', 0.0))

    if f1_score >= threshold:
        return {
            'passed': True,
            'reason': f"F1 {f1_score:.4f} >= threshold {threshold}",
            'score': f1_score
        }
    return {
        'passed': False,
        'reason': f'F1 {f1_score:.4f} < threshold {threshold}',
        'score': f1_score
    }