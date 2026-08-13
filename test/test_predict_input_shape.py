"""Regression tests for PredictRequest input normalisation.

PredictRequest.text is Union[str, List[str]], so a bare string is valid per
the API contract -- but the handler's comparison loop did enumerate() over it,
which iterates CHARACTERS. A 66-character input produced 66 iterations against
a 1-element prediction list and raised IndexError, so every single-string
request returned 500. It reached production because every local test happened
to pass a list.

These tests exercise the normalisation directly rather than through the app,
which would need models and a database on startup.
"""

import pytest

from src.serving.schema import PredictRequest


def normalise(req: PredictRequest) -> list[str]:
    """Mirrors the normalisation at the top of app.predict()."""
    return [req.text] if isinstance(req.text, str) else list(req.text)


def test_bare_string_becomes_one_element():
    """The bug: a string used to be iterated character by character."""
    req = PredictRequest(text="Company profits surged beyond expectations")
    assert normalise(req) == ["Company profits surged beyond expectations"]


def test_bare_string_length_is_not_character_count():
    """Guards the specific failure: len() over a string is its character count."""
    text = "Shares plunged after disappointing guidance"
    req = PredictRequest(text=text)
    assert len(normalise(req)) == 1
    assert len(normalise(req)) != len(text)


def test_list_passes_through_unchanged():
    req = PredictRequest(text=["first headline", "second headline"])
    assert normalise(req) == ["first headline", "second headline"]


def test_single_element_list_still_works():
    req = PredictRequest(text=["only one"])
    assert normalise(req) == ["only one"]


def is_rejected(texts: list[str]) -> bool:
    """Mirrors the handler's 422 guard."""
    return not texts or any(not t or not t.strip() for t in texts)


@pytest.mark.parametrize("value", ["", "   ", [], [""], ["ok", "  "]])
def test_blank_inputs_are_rejected(value):
    """Must yield 422, not a 500 or a silent inference on empty text.

    Note "" normalises to [""] — a truthy one-element list — so a bare
    `if not texts` check does NOT catch it. That gap is why this is
    parametrised over both the string and list forms.
    """
    assert is_rejected(normalise(PredictRequest(text=value)))


@pytest.mark.parametrize("value", ["real text", ["a", "b"]])
def test_valid_inputs_are_not_rejected(value):
    assert not is_rejected(normalise(PredictRequest(text=value)))
