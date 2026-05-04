import argparse
from datetime import datetime, timedelta

from src.drift.storage.factory import get_drift_store
from src.drift.features import build_feature_dataframe
from src.drift.detector import compute_drift, compute_confidence_shift, compute_disagreement
from src.drift.storage.drift_metrics_repository import insert_drift_metric
MIN_SAMPLES = 10

def compute_time_windows(window_hours: float):
    now = datetime.now()

    cur_end = now
    cur_start = now - timedelta(hours = window_hours)

    ref_end = cur_start
    ref_start = ref_end - timedelta(hours = window_hours)

    return ref_start, ref_end, cur_start, cur_end

def run_drift_job(window_hours: float = 1.0) -> dict:
    store = get_drift_store()

    # define windows
    ref_start, ref_end, cur_start, cur_end = compute_time_windows(window_hours)

    # fetch logs
    ref_logs = store.fetch_reference(ref_start.isoformat(), ref_end.isoformat())

    cur_logs = store.fetch_reference(cur_start.isoformat(), cur_end.isoformat())

    print(f'[INFO] Reference size: {len(ref_logs)}')
    print(f'[INFO] Current size: {len(cur_logs)}')

    # guard
    if len(ref_logs) < MIN_SAMPLES or len(cur_logs) < MIN_SAMPLES:
        print('[WARN] Insufficient data for drift computation')
        insert_drift_metric(0.0)
        return {}
    
    # normalize window size
    min_size = min(len(ref_logs), len(cur_logs))
    ref_logs = ref_logs.sample(min_size, random_state=42)
    cur_logs = cur_logs.sample(min_size, random_state=42)


    # feature transformation
    ref_features = build_feature_dataframe(ref_logs)
    cur_features = build_feature_dataframe(cur_logs)

    # predictions
    ref_preds = ref_logs['primary_prediction']
    cur_preds = cur_logs['primary_prediction']

    # compute drift
    result = compute_drift(ref_features, cur_features, ref_preds, cur_preds)
    ref_dis, cur_dis = compute_disagreement(ref_logs, cur_logs)
    ref_conf, cur_conf = compute_confidence_shift(ref_logs, cur_logs)
    
    final_score = result["final_drift_score"]
    print(f'[DEBUG] Writing drift score: {final_score} to drift.db')
    insert_drift_metric(final_score)
    

    
    # output
    print("\n=== DRIFT RESULT ===")
    print({
        "ref_size": len(ref_logs),
        "cur_size": len(cur_logs),
        "feature_drift": result['feature_drift'],
        "prediction_drift": result['prediction_drift'],
        "final_drift_score": result['final_drift_score']
    })

    print("\n=== IMPACT ANALYIS ===")
    print({
        "ref_disagreement": ref_dis,
        "cur_disagreement": cur_dis,
        "ref_confidence": ref_conf,
        "cur_confidence": cur_conf,
        "confidence_drop": ref_conf - cur_conf
    })
    return result

def parse_args():
    parser = argparse.ArgumentParser(description="Run druft detection job")
    parser.add_argument(
        "--window_hours",
        type=int,
        default=1,
        help="Time window (in hours) for drift comparison"
    )
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    res = run_drift_job(window_hours=args.window_hours)
    if res is None:
        print('Something is not right!')