import numpy as np
from scipy.stats import ks_2samp

def compute_feature_drft(reference_df, current_df) -> dict:
    drift_scores = {}
    
    for col in reference_df.columns:
        if col not in current_df.columns:
            continue

        ref = reference_df[col].dropna()
        curr = current_df[col].dropna()

        if len(ref) < 2 or len(curr) < 2:
            drift_scores[col] = 0.0
            continue
        
        stat, _ = ks_2samp(ref, curr)
        drift_scores[col] = stat

    return drift_scores

def aggregate_drift_scores(drift_scores: dict):
    if not drift_scores:
        return 0.0
    return np.mean(list(drift_scores.values()))


def compute_prediction_drift(ref_preds, cur_preds) -> float:
    ref_dist = ref_preds.value_counts(normalize = True)
    cur_dist = cur_preds.value_counts(normalize = True)

    all_labels = set(ref_dist.index).union(set(cur_dist.index))

    diff = 0.0

    for label in all_labels:
        diff += abs(ref_dist.get(label, 0) - cur_dist.get(label, 0))

    return diff /2 # normalize to [0,1] range

def compute_drift(reference_df, current_df, ref_preds, cur_preds) -> dict:
    # compute feature drift
    feature_drift = compute_feature_drft(reference_df, current_df)
    feature_score = aggregate_drift_scores(feature_drift)

    # compute prediction drift
    prediction_score = compute_prediction_drift(ref_preds, cur_preds)

    # aggregate overall drift
    final_score = 0.7 * feature_score + 0.3 * prediction_score

    return {
        'feature_drift': feature_score,
        'prediction_drift': prediction_score,
        'final_drift_score': final_score,
        'per_feature_drift': feature_drift
    }