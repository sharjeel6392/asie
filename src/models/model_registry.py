import yaml
import os
import tempfile
from datetime import datetime
import copy

from src.experiments.schemas import ExperimentResult
from src.logger import configure_logger
from src.constants import MODEL_REGISTRY_FILE

EMPTY_REGISTRY = {"primary": None, "shadow": None, "history": []}


def _s3_registry_uri() -> str | None:
    """S3 URI for the registry file (e.g. 'asie-platform-.../models/model_registry.yaml'),
    or None for local-disk behavior. Gated on ASIE_MODEL_S3_URI so local dev
    (docker-compose, tests) is unaffected — only a real EKS deploy sets it."""
    base = os.getenv("ASIE_MODEL_S3_URI")
    if not base:
        return None
    return f"{base.rstrip('/')}/model_registry.yaml"


def _split_s3_uri(uri: str) -> tuple[str, str]:
    bucket, _, key = uri.partition("/")
    return bucket, key


def load_registry() -> dict:
    s3_uri = _s3_registry_uri()
    if s3_uri:
        import boto3
        from botocore.exceptions import ClientError

        bucket, key = _split_s3_uri(s3_uri)
        s3 = boto3.client("s3")
        try:
            body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
        except ClientError as e:
            if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
                return dict(EMPTY_REGISTRY)
            raise
        return yaml.safe_load(body) or dict(EMPTY_REGISTRY)

    if not os.path.exists(MODEL_REGISTRY_FILE):
        return dict(EMPTY_REGISTRY)

    with open(MODEL_REGISTRY_FILE) as f:
        return yaml.safe_load(f) or dict(EMPTY_REGISTRY)


def save_registry(registry: dict) -> None:
    s3_uri = _s3_registry_uri()
    if s3_uri:
        import boto3

        bucket, key = _split_s3_uri(s3_uri)
        boto3.client("s3").put_object(
            Bucket=bucket, Key=key, Body=yaml.safe_dump(registry).encode("utf-8")
        )
        return

    dir_name = os.path.dirname(MODEL_REGISTRY_FILE)

    with tempfile.NamedTemporaryFile(mode='w', delete=False, dir=dir_name) as tmp:
        yaml.safe_dump(registry, tmp)
        temp_name = tmp.name

    os.replace(temp_name, MODEL_REGISTRY_FILE)

def register_shadow_model(result: ExperimentResult) -> bool:
    """
    Register a model as shadow (candidate) in the model registry.

    - overwrites existing shadow model
    - appens to history with timestamp and metadata
    """
    logger = configure_logger()
    registry = load_registry()
    new_f1 = result.get('metrics',{}).get('eval_f1', 0)

    current_shadow = registry.get('shadow')

    if current_shadow:
        current_f1 = current_shadow['metrics'].get('eval_f1',0)

        if new_f1 <= current_f1:
            logger.info('New model is worse than current shadow. Skipping update.')
            return False

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
    return True

class PromotionBlocked(Exception):
    """The promotion gate refused. Carries the decision so the caller can log
    exactly which criterion failed rather than a bare failure."""

    def __init__(self, decision):
        self.decision = decision
        super().__init__(f"{decision.decision}: {'; '.join(decision.reasons)}")


def promote_to_primary(*, force: bool = False, approved_by: str | None = None) -> dict:
    """
    Promote the current shadow model to primary (production) status.

    Gated by default. This function used to promote unconditionally -- it was
    also never called by anything, so the registry had a promotion mechanism
    with no policy attached. The policy now lives in src/models/promotion.py
    and is evaluated here (DEPLOYMENT_ARCHITECTURE.md §4).

    force=True is the human-approval path, and exists for exactly one case:
    the gate returns HOLD when the candidate disagrees heavily with primary,
    which without ground truth means "the models differ", not "the candidate
    is wrong". A person decides that one. Pass approved_by so the history
    records who, since a forced promotion is the one that will need
    explaining later.

    Note this only updates the registry -- the model is not deployed until
    its run_id is committed to gitops/values/inference.yaml. The registry
    proposes; git disposes (§2).
    """
    from src.models.promotion import evaluate_promotion

    logger = configure_logger()
    registry = load_registry()

    shadow = registry.get("shadow")

    if not shadow:
        raise ValueError("No shadow model to promote")

    decision = evaluate_promotion(registry)
    if not decision.should_promote and not force:
        raise PromotionBlocked(decision)

    entry = {
        **shadow,
        "stage": "primary",
        "promoted_at": datetime.now().isoformat(),
        "promotion_decision": decision.decision,
        "promotion_reasons": decision.reasons,
        "forced": bool(force and not decision.should_promote),
        "approved_by": approved_by,
    }

    registry["primary"] = entry
    registry["history"].append(copy.deepcopy(entry))

    save_registry(registry)
    logger.info(
        "Promoted %s to primary (%s%s)",
        shadow.get("run_id"),
        decision.decision,
        f", forced by {approved_by}" if entry["forced"] else "",
    )
    return entry