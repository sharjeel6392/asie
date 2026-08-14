"""Promotion policy tests — DEPLOYMENT_ARCHITECTURE.md §4.

Evidence is injected rather than read from a database: the policy is the thing
under test, and binding these to a live inference_logs table would make them
slow, order-dependent, and unable to express the cases that matter (a shadow
that fails 30% of requests is not something you can arrange on demand).
"""

import pytest

from src.models.promotion import (
    HOLD,
    INSUFFICIENT_DATA,
    PROMOTE,
    REJECT,
    _percentile,
    evaluate_online_gate,
    evaluate_promotion,
)


def evidence(**overrides):
    """A shadow model that passes every gate, unless a test breaks one."""
    base = {
        "shadow_version": "run_abc",
        "samples": 5000,
        "failures": 0,
        "failure_rate": 0.0,
        "disagreement_rate": 0.05,
        "shadow_p95_latency_ms": 100.0,
        "primary_p95_latency_ms": 100.0,
        "soak_hours": 48.0,
    }
    base.update(overrides)
    return base


def registry(shadow_f1=0.90, primary_f1=0.80, shadow_run="run_new", primary_run="run_old"):
    return {
        "shadow": {"run_id": shadow_run, "metrics": {"eval_f1": shadow_f1}},
        "primary": {"run_id": primary_run, "metrics": {"eval_f1": primary_f1}},
    }


# --------------------------------------------------------------------------
# Online gate — "is it safe"
# --------------------------------------------------------------------------

def test_clean_shadow_promotes():
    assert evaluate_online_gate("run_abc", evidence=evidence()).decision == PROMOTE


def test_too_few_samples_is_insufficient_not_reject():
    # The distinction matters: a candidate with no evidence yet has not failed,
    # and must not be recorded as rejected.
    result = evaluate_online_gate("run_abc", evidence=evidence(samples=12))
    assert result.decision == INSUFFICIENT_DATA
    assert not result.should_promote


def test_enough_samples_but_short_soak_is_insufficient():
    # 5000 samples inside 20 minutes is one traffic pattern, not a
    # representative window -- this is the case min_samples alone cannot catch.
    result = evaluate_online_gate("run_abc", evidence=evidence(soak_hours=0.33))
    assert result.decision == INSUFFICIENT_DATA
    assert "soaked" in result.reasons[0]


def test_shadow_failures_reject():
    result = evaluate_online_gate("run_abc", evidence=evidence(failures=500, failure_rate=0.10))
    assert result.decision == REJECT
    assert "failed" in result.reasons[0]


def test_slow_shadow_rejects_even_though_it_works():
    # Correctness is fine; it is 2x slower. The HPA would hide this by scaling
    # out, so the gate has to catch it.
    result = evaluate_online_gate("run_abc", evidence=evidence(shadow_p95_latency_ms=200.0))
    assert result.decision == REJECT
    assert "latency" in result.reasons[0]


def test_latency_just_inside_limit_passes():
    # 1.25x is the documented limit and must be inclusive, or the threshold
    # silently means "strictly less than 1.25".
    result = evaluate_online_gate("run_abc", evidence=evidence(shadow_p95_latency_ms=125.0))
    assert result.decision == PROMOTE


def test_high_disagreement_holds_rather_than_rejects():
    # The key policy decision: with no ground truth, disagreement means the
    # models differ, not that the candidate is wrong. It must not auto-reject.
    result = evaluate_online_gate("run_abc", evidence=evidence(disagreement_rate=0.55))
    assert result.decision == HOLD
    assert not result.should_promote


def test_failure_outranks_disagreement():
    # A model that is both broken and surprising is broken -- REJECT, not the
    # softer HOLD, or a genuinely failing model could be waved through review.
    result = evaluate_online_gate(
        "run_abc", evidence=evidence(failure_rate=0.5, disagreement_rate=0.9)
    )
    assert result.decision == REJECT


def test_zero_primary_latency_does_not_divide_by_zero():
    result = evaluate_online_gate("run_abc", evidence=evidence(primary_p95_latency_ms=0.0))
    assert result.decision in (PROMOTE, HOLD, REJECT)  # any verdict, but no crash


# --------------------------------------------------------------------------
# Full decision — offline "better" AND online "safe"
# --------------------------------------------------------------------------

def test_worse_offline_model_never_promotes_however_safe_it_looks():
    result = evaluate_promotion(registry(shadow_f1=0.70, primary_f1=0.85), evidence=evidence())
    assert result.decision == REJECT
    assert "eval_f1" in result.reasons[0]


def test_equal_f1_does_not_promote():
    # Ties go to the incumbent: a rollout that cannot demonstrate improvement
    # is pure risk.
    result = evaluate_promotion(registry(shadow_f1=0.85, primary_f1=0.85), evidence=evidence())
    assert result.decision == REJECT


def test_better_offline_and_safe_online_promotes():
    assert evaluate_promotion(registry(), evidence=evidence()).decision == PROMOTE


def test_shadow_same_as_primary_rejects():
    reg = registry(shadow_run="same_run", primary_run="same_run")
    assert evaluate_promotion(reg, evidence=evidence()).decision == REJECT


def test_no_shadow_registered_rejects():
    assert evaluate_promotion({"primary": {"run_id": "x"}}).decision == REJECT


def test_bootstrap_with_no_primary_promotes_on_merit():
    # First model ever: nothing to be worse than, so the offline gate passes
    # and the online gate decides.
    reg = {"shadow": {"run_id": "run_first", "metrics": {"eval_f1": 0.6}}, "primary": None}
    assert evaluate_promotion(reg, evidence=evidence()).decision == PROMOTE


# --------------------------------------------------------------------------
# Percentile helper — computed in Python to avoid SQL dialect branching
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "values,pct,expected",
    [
        ([], 0.95, None),
        ([42.0], 0.95, 42.0),
        (list(range(1, 101)), 0.95, 95.0),
        ([5.0, 1.0, 3.0], 0.5, 3.0),
    ],
)
def test_percentile(values, pct, expected):
    assert _percentile(values, pct) == expected


# --------------------------------------------------------------------------
# Registry transition — the gate is enforced, and force= is the human path
# --------------------------------------------------------------------------

def test_promote_to_primary_is_blocked_by_the_gate(monkeypatch):
    from src.models import model_registry

    reg = registry(shadow_f1=0.5, primary_f1=0.9)  # worse offline
    saved = {}
    monkeypatch.setattr(model_registry, "load_registry", lambda: reg)
    monkeypatch.setattr(model_registry, "save_registry", lambda r: saved.update(r))

    with pytest.raises(model_registry.PromotionBlocked):
        model_registry.promote_to_primary()
    assert saved == {}, "a blocked promotion must not write the registry"


def test_force_overrides_and_records_who_approved(monkeypatch):
    from src.models import model_registry

    reg = registry(shadow_f1=0.5, primary_f1=0.9)
    reg["history"] = []
    saved = {}
    monkeypatch.setattr(model_registry, "load_registry", lambda: reg)
    monkeypatch.setattr(model_registry, "save_registry", lambda r: saved.update(r))

    entry = model_registry.promote_to_primary(force=True, approved_by="sharjeel")
    assert entry["forced"] is True
    assert entry["approved_by"] == "sharjeel"
    assert saved["primary"]["run_id"] == "run_new"
