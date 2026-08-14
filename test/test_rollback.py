"""Automated rollback policy and the GitOps values writer — Day 6.

Both are tested without a cluster, Prometheus, or a git remote: the policy
takes injected health, and the values edit is a pure string function. That
separation is the point — the parts that decide are testable, and the parts
that touch the world are thin.
"""

import pytest

from src.gitops.values_writer import GitOpsWriteError, set_model_version
from src.models.rollback import (
    HEALTHY,
    NO_ACTION,
    ROLLBACK,
    evaluate_rollback,
    previous_primary,
)

VALUES = '''model:
  # Migrated 2026-08-14 from the old fixed prefixes.
  primaryVersion: "run_old"   # eval_f1 0.9715
  shadowVersion: "run_new"    # eval_f1 0.9824
'''


def registry(current="run_b", promoted_at="2026-08-14T12:00:00+00:00", history=None):
    return {
        "primary": {"run_id": current, "promoted_at": promoted_at},
        "history": history
        if history is not None
        else [
            {"stage": "primary", "run_id": "run_a"},
            {"stage": "shadow", "run_id": "run_b"},
            {"stage": "primary", "run_id": "run_b"},
        ],
    }


def health(**kw):
    base = {"request_rate": 5.0, "error_rate_abs": 0.0, "error_ratio": 0.0, "primary_loaded": 1}
    base.update(kw)
    return base


# --------------------------------------------------------------------------
# Values writer — comments must survive, because they are the only record of
# why the values are what they are
# --------------------------------------------------------------------------

def test_sets_version_and_keeps_the_trailing_comment():
    out = set_model_version(VALUES, "primaryVersion", "run_new")
    assert 'primaryVersion: "run_new"   # eval_f1 0.9715' in out
    # the other key is untouched
    assert 'shadowVersion: "run_new"' in out


def test_preserves_surrounding_comments():
    out = set_model_version(VALUES, "primaryVersion", "run_x")
    assert "# Migrated 2026-08-14 from the old fixed prefixes." in out


def test_missing_key_raises_rather_than_silently_doing_nothing():
    with pytest.raises(GitOpsWriteError):
        set_model_version(VALUES, "notAKey", "run_x")


# --------------------------------------------------------------------------
# Which version to roll back TO
# --------------------------------------------------------------------------

def test_previous_primary_skips_the_current_one():
    assert previous_primary(registry()) == "run_a"


def test_previous_primary_ignores_shadow_entries():
    # Rolling "back" onto the shadow would deploy something NEWER than what is
    # failing -- the opposite of a rollback.
    reg = registry(history=[{"stage": "shadow", "run_id": "run_z"}, {"stage": "primary", "run_id": "run_b"}])
    assert previous_primary(reg) is None


# --------------------------------------------------------------------------
# The policy
# --------------------------------------------------------------------------

def test_healthy_primary_does_nothing():
    d = evaluate_rollback(registry(), prometheus_address="http://p", health=health())
    assert d.action == HEALTHY


def test_high_error_ratio_rolls_back_to_previous():
    d = evaluate_rollback(
        registry(), prometheus_address="http://p", health=health(error_ratio=0.4)
    )
    assert d.action == ROLLBACK
    assert d.target_version == "run_a"


def test_model_not_loaded_rolls_back():
    d = evaluate_rollback(
        registry(), prometheus_address="http://p", health=health(primary_loaded=0)
    )
    assert d.action == ROLLBACK


def test_low_traffic_does_not_roll_back_on_a_ratio():
    # One failure out of three requests is 33% and means nothing. Without this
    # floor every quiet night becomes a deploy.
    d = evaluate_rollback(
        registry(),
        prometheus_address="http://p",
        health=health(request_rate=0.001, error_ratio=0.5),
    )
    assert d.action == NO_ACTION
    assert "not enough traffic" in d.reasons[0]


def test_old_primary_is_not_rolled_back():
    # THE key guard. A model healthy for days that suddenly errors is far more
    # likely a platform failure, which a rollback cannot fix -- it would just
    # add a deploy to an ongoing incident.
    d = evaluate_rollback(
        registry(promoted_at="2026-08-01T00:00:00+00:00"),
        prometheus_address="http://p",
        health=health(error_ratio=0.9),
    )
    assert d.action == NO_ACTION
    assert "unlikely to be the model" in d.reasons[0]


def test_no_previous_version_means_no_rollback_even_when_broken():
    reg = registry(history=[{"stage": "primary", "run_id": "run_b"}])
    d = evaluate_rollback(reg, prometheus_address="http://p", health=health(error_ratio=0.9))
    assert d.action == NO_ACTION
    assert "no previous primary" in d.reasons[0]


def test_no_primary_recorded():
    d = evaluate_rollback({}, prometheus_address="http://p", health=health())
    assert d.action == NO_ACTION


def test_zero_traffic_is_not_treated_as_zero_errors():
    # request_rate None means nothing was served. That must not read as
    # healthy, which is what a naive `errors/total or 0` would produce.
    d = evaluate_rollback(
        registry(), prometheus_address="http://p", health=health(request_rate=None, error_ratio=None)
    )
    assert d.action == NO_ACTION
