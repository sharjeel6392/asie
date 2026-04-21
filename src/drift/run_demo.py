import requests
from src.drift.worker import run_drift_job
from src.drift.demo_data import NORMAL_DATA, SLANG_DATA, EXTREME_DATA
import time

API_URL = "http://localhost:8000/predict"

def send_request(text: str):
    response = requests.post(API_URL, json={"text": [text]})
    return response.json()

def inject_and_run(data, label):
    print(f"=== {label} ===")
    _ = send_request(data)
    result = run_drift_job(window_hours=0.5)

    print(f'\nDrift Score: {result.get("final_drift_score")}')
    time.sleep(10)

if __name__ == "__main__":
    # Baseline
    for i in range(len(NORMAL_DATA)):
        inject_and_run(NORMAL_DATA[i], str(i+1)+"th BASELINE")

    # Gradual drift
    for i in range(len(SLANG_DATA)):
        inject_and_run(SLANG_DATA[i], str(i+1)+"th SLANG ")
    
    # Extreme drift
    for i in range(len(EXTREME_DATA)):
        inject_and_run(EXTREME_DATA[i], str(i + 1)+"th EXTREME")