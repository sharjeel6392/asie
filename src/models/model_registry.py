import yaml
import os
import tempfile
from datetime import datetime
import copy

from src.experiments.schemas import ExperimentResult
from src.logger import logging
from src.constants import REGISTRY_PATH


def load_registry() -> dict:
    if not os.path.exists(REGISTRY_PATH):
        return {
            "primary": None,
            "shadow": None,
            "history": [] 
            }
    
    with open(REGISTRY_PATH) as f:
        return yaml.safe_load(f) or {
            "production": None,
            "shadow": None,
            "history": []
            }

def save_registry(registry: dict) -> None:
    dir_name = os.path.dirname(REGISTRY_PATH)

    with tempfile.NamedTemporaryFile(mode='w', delete=False, dir=dir_name) as tmp:
        yaml.safe_dump(registry, tmp)
        temp_name = tmp.name
    
    os.replace(temp_name, REGISTRY_PATH)

def register_shadow_model(result: ExperimentResult) -> None:
    """
    Register a model as shadow (candidate) in the model registry.

    - overwrites existing shadow model
    - appens to history with timestamp and metadata
    """

    registry = load_registry()
    new_f1 = result.get('metrics',{}).get('eval_f1', 0)

    current_shadow = registry.get('shadow')

    if current_shadow:
        current_f1 = current_shadow['metrics'].get('eval_f1',0)

        if new_f1 <= current_f1:
            logging.info('New model is worse than current shadow. Skipping update.')
            return

    entry = {
        "run_id": result.get("run_id"),
        "metrics": result.get("metrics"),
        "config": result.get("config"),
        "stage": "shadow",
        "registered_at": datetime.now().isoformat()
    }

    # overwrite existing shadow
    registry["shadow"] = entry

    # append to history
    registry["history"].append(copy.deepcopy(entry))

    # BOOTSTRAP LOGIC
    if registry["primary"] is None:
        primary_entry = {
            **entry,
            "stage": "primary",
            "promoted_at": datetime.now().isoformat()
        }
        registry["primary"] = primary_entry
        registry["history"].append(copy.deepcopy(primary_entry))

    save_registry(registry)

def promote_to_primary() -> None:
    """
    Promote the current shadow model to primary (production) status.
    
    - moves current shadow to primary
    - appends promotion event to history
    """
    registry = load_registry()

    shadow = registry.get("shadow")

    if not shadow:
        raise ValueError("No shadow model to promote")
    
    entry = {
        **shadow,
        "stage": "primary",
        "promoted_at": datetime.now().isoformat()
    }

    registry["primary"] = entry
    registry["history"].append(entry)

    save_registry(registry)