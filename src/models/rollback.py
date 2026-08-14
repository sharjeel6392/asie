"""Automated rollback — DEPLOYMENT_ARCHITECTURE.md §5, Layer 2.

Layer 0 (probes) stops a model that cannot load from ever taking traffic, and
Day 5's canary analysis aborts a bad version mid-rollout. Both act *during* a
deploy. This covers the case neither does: a version that started healthy,
passed its canary, and degraded afterwards.

Polling, not push. Alertmanager can post a webhook, but its payload does not
match Airflow's DAG-trigger schema, so a push design needs an adapter service
sitting between them — a new deployable whose own failure is silent, since
nothing notices a rollback trigger that never arrives. Polling reuses Airflow
and Prometheus, both already running, and degrades honestly: if the scheduler
is down, nothing rolls back and the scheduler being down is itself alerted.
The cost is latency bounded by the DAG schedule.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import requests

from src.constants import (
    ROLLBACK_ERROR_RATE_THRESHOLD,
    ROLLBACK_MAX_AGE_HOURS,
    ROLLBACK_MIN_REQUESTS,
)
from src.logger import configure_logger

ROLLBACK = "rollback"
HEALTHY = "healthy"
NO_ACTION = "no_action"


@dataclass
class RollbackDecision:
    action: str
    reasons: list[str] = field(default_factory=list)
    target_version: str | None = None
    metrics: dict = field(default_factory=dict)

    @property
    def should_rollback(self) -> bool:
        return self.action == ROLLBACK


def query_prometheus(address: str, query: str) -> float | None:
    """Single scalar from an instant query, or None if there is no sample.

    None and 0.0 are kept distinct on purpose: "no requests were served" and
    "no requests failed" are the same number and opposite meanings, and
    conflating them would let a pod serving nothing at all read as perfectly
    healthy.
    """
    resp = requests.get(
        f"{address.rstrip('/')}/api/v1/query", params={"query": query}, timeout=15
    )
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("status") != "success":
        raise RuntimeError(f"prometheus query failed: {payload.get('error')}")
    result = payload["data"]["result"]
    if not result:
        return None
    return float(result[0]["value"][1])


def collect_health(address: str, window: str = "5m") -> dict:
    """Error rate, request volume and model-loaded state for the live primary."""
    total = query_prometheus(
        address, f'sum(rate(asie_http_requests_total{{route="/predict"}}[{window}]))'
    )
    errors = query_prometheus(
        address,
        f'sum(rate(asie_http_requests_total{{route="/predict",status=~"5.."}}[{window}]))',
    )
    loaded = query_prometheus(address, 'min(asie_model_loaded{role="primary"})')

    return {
        "request_rate": total,
        "error_rate_abs": errors,
        "error_ratio": (errors / total) if (total and errors is not None) else None,
        "primary_loaded": loaded,
        "window": window,
    }


def _age_hours(promoted_at: str | None) -> float | None:
    if not promoted_at:
        return None
    try:
        ts = datetime.fromisoformat(promoted_at)
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - ts).total_seconds() / 3600.0


def previous_primary(registry: dict) -> str | None:
    """The run_id that was primary before the current one.

    Read from history rather than from `shadow`: the shadow is the *next*
    candidate, and rolling "back" onto it would deploy something newer than
    what is failing.
    """
    current = (registry.get("primary") or {}).get("run_id")
    primaries = [
        h.get("run_id")
        for h in registry.get("history", [])
        if h.get("stage") == "primary" and h.get("run_id")
    ]
    for run_id in reversed(primaries):
        if run_id != current:
            return run_id
    return None


def evaluate_rollback(
    registry: dict,
    *,
    prometheus_address: str,
    health: dict | None = None,
    error_rate_threshold: float = ROLLBACK_ERROR_RATE_THRESHOLD,
    min_requests: float = ROLLBACK_MIN_REQUESTS,
    max_age_hours: float = ROLLBACK_MAX_AGE_HOURS,
) -> RollbackDecision:
    """Decide whether the live primary should be rolled back.

    `health` is injectable so the policy is testable without Prometheus.
    """
    logger = configure_logger()
    primary = registry.get("primary") or {}
    current = primary.get("run_id")
    if not current:
        return RollbackDecision(NO_ACTION, ["no primary model recorded"])

    ev = health if health is not None else collect_health(prometheus_address)
    ev["current_version"] = current

    # The single most important guard. A model that has served correctly for
    # days and suddenly errors is far more likely a platform failure -- RDS
    # unreachable, a node dying, S3 throttling -- than a model defect that
    # waited three days to appear. Rolling back the model would not fix any of
    # those, and would add a deploy to an ongoing incident. Automated rollback
    # is only appropriate close to a change, where the change is the most
    # probable cause.
    age = _age_hours(primary.get("promoted_at"))
    ev["primary_age_hours"] = age
    if age is not None and age > max_age_hours:
        return RollbackDecision(
            NO_ACTION,
            [
                f"primary has been live {age:.1f}h (>{max_age_hours}h); "
                "degradation this long after deploy is unlikely to be the model — "
                "not rolling back into an incident"
            ],
            metrics=ev,
        )

    target = previous_primary(registry)

    # model_loaded == 0 means the pod is up but has no usable model. Probes
    # should have caught it, so reaching here means it broke after startup.
    if ev.get("primary_loaded") == 0:
        return RollbackDecision(
            ROLLBACK if target else NO_ACTION,
            ["primary model reports not loaded"]
            + ([] if target else ["but no previous primary exists to roll back to"]),
            target_version=target,
            metrics=ev,
        )

    rate = ev.get("request_rate")
    if rate is None or rate < min_requests:
        # Too little traffic for the ratio to mean anything. Rolling back on
        # one failed request out of three would make every quiet period a
        # deploy event.
        return RollbackDecision(
            NO_ACTION,
            [f"request rate {rate} below {min_requests}/s — not enough traffic to judge"],
            metrics=ev,
        )

    ratio = ev.get("error_ratio")
    if ratio is not None and ratio > error_rate_threshold:
        if not target:
            return RollbackDecision(
                NO_ACTION,
                [f"error ratio {ratio:.1%} over threshold but no previous primary to roll back to"],
                metrics=ev,
            )
        logger.warning("rollback triggered: error ratio %.1f%% on %s", ratio * 100, current)
        return RollbackDecision(
            ROLLBACK,
            [
                f"error ratio {ratio:.1%} over {error_rate_threshold:.1%} "
                f"at {rate:.2f} req/s, {age:.2f}h after deploy" if age is not None
                else f"error ratio {ratio:.1%} over {error_rate_threshold:.1%}"
            ],
            target_version=target,
            metrics=ev,
        )

    return RollbackDecision(HEALTHY, [f"error ratio {ratio if ratio is not None else 0:.1%}"], metrics=ev)
