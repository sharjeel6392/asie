#!/usr/bin/env python
"""Debug script to test retraining pipeline directly and capture errors."""

import sys
import os
import traceback
import logging

# Add ASIE to path
sys.path.insert(0, '/mnt/e/ASIE')

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Force MLflow tracking
os.environ["MLFLOW_TRACKING_URI"] = "sqlite:////home/kirksalvator/mlflow.db"

print("=" * 80)
print("STARTING PIPELINE DEBUG TEST")
print("=" * 80)
print(f"CWD: {os.getcwd()}")
print(f"PYTHONPATH includes: {sys.path[:3]}")
print()

try:
    print("Step 1: Importing modules...")
    from src.pipelines.retraining_pipeline import retraining_pipeline
    from src.logger import configure_logger
    print("✓ Imports successful")
    
    print("\nStep 2: Configuring logger...")
    logger = configure_logger()
    logger.info("Logger configured")
    print("✓ Logger configured")
    
    print("\nStep 3: Running retraining pipeline...")
    configs = [
        {
            'lr': 2e-5,
            'epochs': 1,
            'batch_size': 8,
            'model_type': 'transformer',
            'model_name': 'distilbert-base-uncased'
        }
    ]
    
    result = retraining_pipeline(configs)
    print(f"✓ Pipeline completed with result: {result}")
    
except Exception as e:
    print("\n" + "=" * 80)
    print("ERROR OCCURRED:")
    print("=" * 80)
    print(f"Error Type: {type(e).__name__}")
    print(f"Error Message: {str(e)}")
    print("\nFull Traceback:")
    print(traceback.format_exc())
    print("=" * 80)
    sys.exit(1)

print("\n" + "=" * 80)
print("DEBUG TEST COMPLETED SUCCESSFULLY")
print("=" * 80)
