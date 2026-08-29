from __future__ import annotations

import pytest

from g2lex.audit import audit_runtime_representation
from g2lex.builder import build_implicit_lexicon
from g2lex.selectors.forest import RandomForestSelector
from g2lex.selectors.gbdt import GradientBoostedTreeSelector
from g2lex.selectors.logistic import HashedLogisticSelector
from g2lex.selectors.priority import StaticPrioritySelector
from g2lex.selectors.tree import TreeSelector
from g2lex.value import WORD_ONLY, TaggedValue
from g2lex.verify_exact import compare, verify_typed


def test_verify_typed_reports_each_mismatch_category() -> None:
    source = {
        "missing": "m",
        "shape": "x",
        "order": ("x", "y"),
        "tags": TaggedValue((("A", "a"),)),
        "null": TaggedValue((("A", None),)),
        "different": "left",
        "same": WORD_ONLY,
    }
    actual = {
        "only-extra": "e",
        "shape": ("x",),
        "order": ("y", "x"),
        "tags": TaggedValue((("B", "a"),)),
        "null": TaggedValue((("A", "value"),)),
        "different": "right",
        "same": WORD_ONLY,
    }
    result = verify_typed(actual, source)
    assert result["missing"] == 1
    assert result["extra"] == 1
    assert result["shape_mismatch"] == 1
    assert result["variant_order_mismatch"] == 1
    assert result["tag_mismatch"] == 1
    assert result["null_mismatch"] == 2
    assert result["value_mismatch"] == 4
    assert result["lossless"] is False
    assert verify_typed({"same": "x"}, {"same": "x"})["value_mismatch"] == 0
    compared = compare({"a": "x"}, {"b": "y"})
    assert compared.as_dict() == {
        "only_a": 1,
        "only_b": 1,
        "same": 0,
        "different": 0,
        "shape_different": 0,
    }
    compared = compare({"a": "x", "c": "z"}, {"b": "y", "c": "q"})
    assert compared.only_a == 1 and compared.only_b == 1 and compared.different == 1


def test_audit_valid_nested_and_forbidden_runtime_structures() -> None:
    candidate = build_implicit_lexicon(
        __import__("g2lex.model", fromlist=["LexiconData"]).LexiconData.from_pairs(
            ("a", "x"), ("b", "y"), ("ab", "xy")
        )
    ).asset
    report = audit_runtime_representation(candidate)
    assert report["checked"] is True
    assert report["per_generated_word_recipe_count"] == 0
    candidate.metadata["nested"] = {"values": ["safe", {"key": 1}]}
    assert audit_runtime_representation(candidate)["checked"] is True
    candidate.metadata["recipe_by_word"] = {"ab": "bad"}
    with pytest.raises(AssertionError, match="forbidden"):
        audit_runtime_representation(candidate)

    candidate.metadata.pop("recipe_by_word")
    candidate.metadata["nonserial"] = object()
    with pytest.raises(TypeError):
        audit_runtime_representation(candidate)


def test_selector_reexport_smoke_imports() -> None:
    assert RandomForestSelector and GradientBoostedTreeSelector
    assert HashedLogisticSelector and StaticPrioritySelector and TreeSelector
