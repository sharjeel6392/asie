"""Promotion policy — decides whether the shadow model may become primary.

Implements DEPLOYMENT_ARCHITECTURE.md §4. The policy splits on a constraint
that is easy to miss: `true_label` is NULL for every production row in
inference_logs. There is no ground truth online, so online evidence can
establish that a candidate is SAFE, never that it is BETTER.

    offline (MLflow eval_f1, held-out set)  ->  decides "better"
    online  (inference_logs, live traffic)  ->  decides "safe"

Both must pass. This module owns the decision; it does not perform it —
promote() in model_registry.py does the registry bookkeeping, and the actual
deployment is a commit to gitops/values/inference.yaml. Keeping the decision
separate is what makes it testable without S3, MLflow, or a cluster.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import text

from src.constants import (
    PROMOTION_DISAGREEMENT_REVIEW_RATE,
    PROMOTION_LATENCY_RATIO_LIMIT,
    PROMOTION_MAX_SHADOW_FAILURE_RATE,
    PROMOTION_MIN_SAMPLES,
    PROMOTION_MIN_SOAK_HOURS,
)
from src.db.engine import get_connection
from src.logger import configure_logger

# Decision values. HOLD is distinct from REJECT on purpose: REJECT means the
# candidate is worse and should not be promoted, HOLD means the evidence is
# ambiguous and a person should look. Collapsing them would hide the one case
# where automation genuinely cannot decide.
PROMOTE = "promote"
HOLD = "hold"
REJECT = "reject"
INSUFFICIENT_DATA = "insufficient_data"


@dataclass
class PromotionDecision:
    decision: str
    reasons: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    @property
    def should_promote(self) -> bool:
        return self.decision == PROMOTE


def _percentile(values: list[float], pct: float) -> float | None:
    """Nearest-rank percentile.

    Computed in Python rather than SQL deliberately: Postgres has
    percentile_cont, SQLite has nothing equivalent, and src/db/engine.py's
    whole premise is one code path for both backends with no dialect
    branching. The cost is pulling the latency columns for the window, which
    is bounded by the soak size (thousands of rows, not millions).
    """
    if not values:
        return None
    ordered = sorted(values)
    # ceil, not round: rank = ceil(pct * N) is the nearest-rank definition, and
    # round() here would hit Python's banker's rounding on exact .5 ranks --
    # for N=100 at p95 that rounded 95.5 up to 96 and returned the 96th value.
    idx = min(math.ceil(pct * len(ordered)) - 1, len(ordered) - 1)
    return ordered[max(idx, 0)]


def _as_datetime(value) -> datetime | None:
    """Normalize a timestamp column across backends.

    Postgres (TIMESTAMPTZ) hands back a datetime; SQLite stores TEXT and hands
    back an ISO string. Both reach this function, so neither caller nor query
    needs to know which database it is talking to.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def collect_shadow_evidence(shadow_version: str) -> dict:
    """Aggregate one shadow model's live performance from inference_logs.

    Scoped by shadow_model_version, which is only meaningful because that
    column now carries the real run_id (DEPLOYMENT_ARCHITECTURE.md §6.2).
    While it was a hardcoded constant, this query would have mixed every
    shadow model that ever ran into one set of statistics.
    """
    sql = text(
        """
        SELECT shadow_predictions,
               shadow_latency_ms,
               primary_latency_ms,
               disagreement,
               timestamp
        FROM inference_logs
        WHERE shadow_model_version = :shadow_version
        """
    )

    with get_connection() as conn:
        rows = conn.execute(sql, {"shadow_version": shadow_version}).fetchall()

    total = len(rows)
    # A shadow exception is caught in /predict and written as NULL rather than
    # failing the user's request, so this column is already an error counter.
    failures = sum(1 for r in rows if r[0] is None)
    shadow_latencies = [float(r[1]) for r in rows if r[1] is not None]
    primary_latencies = [float(r[2]) for r in rows if r[2] is not None]
    disagreements = sum(1 for r in rows if r[3])

    timestamps = [ts for ts in (_as_datetime(r[4]) for r in rows) if ts is not None]
    soak_hours = 0.0
    if len(timestamps) >= 2:
        soak_hours = (max(timestamps) - min(timestamps)).total_seconds() / 3600.0

    scored = total - failures
    return {
        "shadow_version": shadow_version,
        "samples": total,
        "failures": failures,
        "failure_rate": (failures / total) if total else 0.0,
        # Denominator is scored rows, not all rows: a failed shadow row has no
        # prediction to agree or disagree with, and counting it as agreement
        # would make a badly broken model look reassuringly consistent.
        "disagreement_rate": (disagreements / scored) if scored else 0.0,
        "shadow_p95_latency_ms": _percentile(shadow_latencies, 0.95),
        "primary_p95_latency_ms": _percentile(primary_latencies, 0.95),
        "soak_hours": soak_hours,
    }


def evaluate_online_gate(
    shadow_version: str,
    *,
    min_samples: int = PROMOTION_MIN_SAMPLES,
    min_soak_hours: float = PROMOTION_MIN_SOAK_HOURS,
    max_failure_rate: float = PROMOTION_MAX_SHADOW_FAILURE_RATE,
    latency_ratio_limit: float = PROMOTION_LATENCY_RATIO_LIMIT,
    disagreement_review_rate: float = PROMOTION_DISAGREEMENT_REVIEW_RATE,
    evidence: dict | None = None,
) -> PromotionDecision:
    """Is this shadow model SAFE to promote? (Not: is it better.)

    `evidence` is injectable so the policy can be tested without a database.
    """
    ev = evidence if evidence is not None else collect_shadow_evidence(shadow_version)
    reasons: list[str] = []

    # Volume first. Every rate below is meaningless underneath it, and
    # reporting "0% failures" from six requests would be actively misleading.
    if ev["samples"] < min_samples:
        return PromotionDecision(
            INSUFFICIENT_DATA,
            [f"only {ev['samples']} shadow predictions, need {min_samples}"],
            ev,
        )

    # Sample count alone can be satisfied by a traffic spike inside a few
    # minutes, which is one workload pattern rather than a representative one.
    if ev["soak_hours"] < min_soak_hours:
        return PromotionDecision(
            INSUFFICIENT_DATA,
            [f"soaked {ev['soak_hours']:.1f}h, need {min_soak_hours}h"],
            ev,
        )

    if ev["failure_rate"] > max_failure_rate:
        reasons.append(
            f"shadow failed on {ev['failure_rate']:.1%} of requests "
            f"(limit {max_failure_rate:.1%})"
        )

    shadow_p95 = ev["shadow_p95_latency_ms"]
    primary_p95 = ev["primary_p95_latency_ms"]
    if shadow_p95 is not None and primary_p95:
        ratio = shadow_p95 / primary_p95
        ev["latency_ratio"] = ratio
        if ratio > latency_ratio_limit:
            # A more accurate but materially slower model still breaks the
            # serving SLO, and the HPA would mask it by scaling out — turning
            # a latency regression into a silent cost increase.
            reasons.append(
                f"shadow p95 latency is {ratio:.2f}x primary "
                f"(limit {latency_ratio_limit}x)"
            )

    if reasons:
        return PromotionDecision(REJECT, reasons, ev)

    # Disagreement is deliberately last and deliberately not a rejection.
    # Without ground truth it means the models differ, not that the candidate
    # is wrong — the candidate may well be the correct one. It is a surprise
    # detector, and the honest response to a big surprise is human review.
    if ev["disagreement_rate"] > disagreement_review_rate:
        return PromotionDecision(
            HOLD,
            [
                f"disagrees with primary on {ev['disagreement_rate']:.1%} of requests "
                f"(review above {disagreement_review_rate:.1%}); "
                "no ground truth online, so this needs a human"
            ],
            ev,
        )

    return PromotionDecision(
        PROMOTE,
        [
            f"{ev['samples']} samples over {ev['soak_hours']:.1f}h, "
            f"{ev['failure_rate']:.2%} failures, "
            f"{ev['disagreement_rate']:.1%} disagreement"
        ],
        ev,
    )


def evaluate_promotion(registry: dict, *, evidence: dict | None = None, **gate_kwargs) -> PromotionDecision:
    """Full promotion decision: offline 'better' AND online 'safe'.

    Note the offline comparison here is shadow vs **primary**, which is not the
    same gate register_shadow_model() applies. That one compares a new
    candidate against the current *shadow* — so a model can legitimately be
    registered as the best candidate so far while still being worse than what
    is actually serving. Promoting on the registration gate alone would
    regress production.
    """
    logger = configure_logger()

    shadow = registry.get("shadow")
    if not shadow:
        return PromotionDecision(REJECT, ["no shadow model registered"], {})

    shadow_version = shadow.get("run_id")
    if not shadow_version:
        return PromotionDecision(REJECT, ["shadow entry has no run_id"], {})

    primary = registry.get("primary")
    if primary and primary.get("run_id") == shadow_version:
        return PromotionDecision(
            REJECT, ["shadow and primary are the same model"], {"shadow_version": shadow_version}
        )

    shadow_f1 = (shadow.get("metrics") or {}).get("eval_f1", 0)
    primary_f1 = (primary.get("metrics") or {}).get("eval_f1", 0) if primary else 0
    if shadow_f1 <= primary_f1:
        return PromotionDecision(
            REJECT,
            [f"offline eval_f1 {shadow_f1} does not beat primary's {primary_f1}"],
            {"shadow_version": shadow_version, "shadow_eval_f1": shadow_f1, "primary_eval_f1": primary_f1},
        )

    decision = evaluate_online_gate(shadow_version, evidence=evidence, **gate_kwargs)
    decision.metrics.setdefault("shadow_eval_f1", shadow_f1)
    decision.metrics.setdefault("primary_eval_f1", primary_f1)

    logger.info(
        "Promotion decision for %s: %s (%s)",
        shadow_version,
        decision.decision,
        "; ".join(decision.reasons),
    )
    return decision
