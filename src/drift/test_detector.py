from datetime import datetime, timedelta

from src.drift.storage.factory import get_drift_store
from src.drift.features import build_feature_dataframe
from src.drift.detector import compute_drift

storage = get_drift_store()

# Reference Window (older data)
ref_end = datetime.now() - timedelta(minutes = 10)
ref_start = ref_end - timedelta(hours=48)

# Current Window (recent data)
cur_end = datetime.now()
cur_start = cur_end - timedelta(hours=1)

# Fetch raw logs
ref_logs = storage.fetch_reference(
    ref_start.isoformat(),
    ref_end.isoformat()
)

cur_logs = storage.fetch_current(
    cur_start.isoformat(),
    cur_end.isoformat() 
)

print(f"Reference logs: {ref_logs.shape}, \nCurrent logs: {cur_logs.shape}")

# Convert to feature DataFrames
ref_features = build_feature_dataframe(ref_logs)
cur_features = build_feature_dataframe(cur_logs)

print(f"Reference features: {ref_features.shape}, \nCurrent features: {cur_features.shape}")

ref_preds = ref_logs['primary_prediction']
cur_preds = cur_logs['primary_prediction']

# Compute drift
result = compute_drift(ref_features, cur_features, ref_preds, cur_preds)

print("Drift Detection Result:")
print("Feature Drift Score: ", result['feature_drift'])
print("Prediction Drift Score: ", result['prediction_drift'])
print("Final Drift Score: ", result['final_drift_score'])

print("Per Feature Drift:")
for k, v in result['per_feature_drift'].items():
    print(f'{k}: {v:.4f}')

