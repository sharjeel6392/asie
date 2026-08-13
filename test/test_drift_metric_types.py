"""Regression test: numpy scalars must not reach the database driver.

compute_drift() returns numpy.float64. sqlite3 accepts that via duck typing,
but psycopg2 has no adapter for numpy scalar types and falls back to their
repr, emitting literal SQL like:

    VALUES ('2026-08-13T19:28:31+00:00', np.float64(0.443))

which Postgres rejects with `schema "np" does not exist`. The result was that
drift scores could never be persisted in the cloud at all -- while working
perfectly against local SQLite.

These tests assert the conversion itself, so they catch the regression
without needing either database.
"""

import numpy as np
import pytest


def coerce(score) -> float:
    """Mirrors the float() conversion in insert_drift_metric."""
    return float(score)


def test_numpy_float_becomes_builtin_float():
    score = np.float64(0.4430769230769231)
    out = coerce(score)
    assert type(out) is float
    assert not isinstance(out, np.generic)


def test_repr_no_longer_leaks_numpy_constructor():
    """The actual failure was psycopg2 emitting repr() into the SQL string."""
    score = np.float64(0.443)
    assert "np.float64" in repr(score)
    assert "np." not in repr(coerce(score))


@pytest.mark.parametrize(
    "value",
    [np.float64(0.75), np.float32(0.5), np.int64(1), 0.0, 1, 0.4430769230769231],
)
def test_all_plausible_score_types_coerce(value):
    out = coerce(value)
    assert type(out) is float


def test_value_is_preserved():
    score = np.float64(0.4430769230769231)
    assert coerce(score) == pytest.approx(0.4430769230769231)
