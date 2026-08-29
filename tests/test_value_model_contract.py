"""Focused typed-value and model contract coverage."""

from __future__ import annotations

import pytest

from g2lex.model import LexiconData
from g2lex.value import (
    WORD_ONLY,
    TaggedValue,
    canonical_bytes,
    logical_sha256,
    validate_selector_value,
    validate_value,
)


def test_all_supported_value_shapes_validate() -> None:
    values = (
        WORD_ONLY,
        "pronunciation",
        ("first", "second"),
        TaggedValue((("DEFAULT", None), ("ALT", ("x", "y")))),
    )
    for value in values:
        validate_value(value)

    validate_selector_value(None)
    validate_selector_value("default")
    validate_selector_value(("first", "second"))


def test_invalid_value_shapes_and_empty_tags_are_rejected() -> None:
    for value in (None, ["x"], {"tag": "x"}, 42):
        with pytest.raises(TypeError):
            validate_value(value)
    for value in (["x"], {"nested": "x"}, 42):
        with pytest.raises(TypeError):
            validate_selector_value(value)
    with pytest.raises(ValueError, match="empty"):
        TaggedValue((("", "value"),))
    with pytest.raises(ValueError, match="duplicate"):
        TaggedValue((("tag", "one"), ("tag", "two")))


def test_canonical_bytes_and_hashes_are_deterministic_and_sorted() -> None:
    first = {"b": ("y",), "a": WORD_ONLY}
    second = {"a": WORD_ONLY, "b": ("y",)}

    assert canonical_bytes(first) == canonical_bytes(second)
    assert logical_sha256(first) == logical_sha256(second)
    with pytest.raises(TypeError, match="keys"):
        canonical_bytes({1: "bad"})  # type: ignore[dict-item]


def test_lexicon_data_runtime_unique_and_counts() -> None:
    data = LexiconData.from_pairs(("word", "x"), ("word", "x"), ("word", "y"))

    assert data.variant_count == 3
    assert data.lookup_all("missing") == ()
    assert not data.is_known("missing")
    unique = data.runtime_unique()
    assert unique.entries == {"word": ("x", "y")}
    assert unique.metadata["view"] == "runtime_unique"
