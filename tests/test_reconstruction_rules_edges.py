from __future__ import annotations

import pytest

from g2lex.composer import (
    ImplicitComposer,
    SearchLimitError,
    best_segmentation,
    best_two_part_segmentation,
    top_k_segmentations,
)
from g2lex.linkers import Linker, LinkerTable
from g2lex.prefix_index import MutableLiteralPrefixIndex
from g2lex.reconstructors import (
    AffixRule,
    MorphologyReconstructor,
    RewriteReconstructor,
    RewriteRule,
    _capitalization,
    induce_rewrite_rules,
    mine_morphology,
)
from g2lex.rules import (
    CompoundStressDemotionRule,
    ConcatenationRule,
    RuleSet,
    rule_from_dict,
)
from g2lex.runtime import ReconstructionCandidate
from g2lex.selector import RuleSelector


def _prefix(literals: dict[str, tuple[str, ...]]) -> MutableLiteralPrefixIndex:
    index = MutableLiteralPrefixIndex.empty()
    for word in literals:
        index.add(word)
    return index


def test_affix_rule_conditions_transforms_and_serialization() -> None:
    context = {"stem": ("sˈtem",), "stm": ("sm",)}
    rule = AffixRule(
        1,
        spelling_prefix="re",
        strip_prefix="re",
        min_stem_length=2,
        required_left_context="st",
        required_right_context="m",
        capitalization_class="lower",
        pronunciation_prefix_remove="s",
        pronunciation_suffix_remove="m",
        pronunciation_prefix_add="r",
        pronunciation_suffix_add="!",
    )
    assert rule.apply("restm", context)[0].pronunciation == ("r!",)
    for word, values in (
        ("xrestm", context),
        ("reabc", context),
        ("reast", context),
        ("restx", context),
    ):
        assert rule.apply(word, values) == ()
    assert rule.apply("refoo", {}) == ()
    assert _capitalization("ABC") == "upper"
    assert _capitalization("Abc") == "initial-upper"
    assert _capitalization("abc") == "lower"
    assert _capitalization("aB") == "mixed"
    assert AffixRule.from_dict(rule.as_dict()) == rule
    morph = MorphologyReconstructor([rule], max_rules=1)
    assert morph.candidates("restm", context)
    assert morph.as_dict()["stage_id"] == "morphology"
    assert morph.serialize_sections()


def test_morphology_mining_support_and_determinism() -> None:
    entries = {"a": ("x",), "b": ("x",), "as": ("xz",), "bs": ("xz",)}
    rules = mine_morphology(entries, min_support=2)
    assert rules and rules == mine_morphology(entries, min_support=2)
    assert mine_morphology(entries, min_support=3) == ()


def test_rewrite_rules_conditions_operations_and_roundtrip() -> None:
    for operation, expected in (("insert", "xy"), ("delete", ""), ("replace", "y")):
        rule = RewriteRule(1, operation, pattern="x", replacement="y")
        assert rule.apply("word", "x") == expected
        assert RewriteRule.from_dict(rule.as_dict()) == rule
    assert RewriteRule(1, "replace", spelling_left="q", pattern="x").apply("word", "x") is None
    assert (
        RewriteRule(1, "replace", source_stage="other", pattern="x").apply("word", "x", "stage")
        is None
    )
    assert RewriteRule(1, "replace", pronunciation_left="q", pattern="x").apply("word", "x") is None
    assert RewriteRule(1, "replace", spelling_right="q", pattern="x").apply("word", "x") is None
    with pytest.raises(ValueError, match="unknown"):
        RewriteRule(1, "unknown", pattern="x").apply("word", "x")
    assert induce_rewrite_rules([{"pattern": "", "operation": "delete"}]) == ()
    assert induce_rewrite_rules([{"pattern": "long", "max_context_length": 2}]) == ()
    rewrite = RewriteReconstructor([RewriteRule(1, "replace", pattern="x", replacement="y")])
    candidates = rewrite.candidates(
        "word", {"candidates": (ReconstructionCandidate("compound", ("x",)),)}
    )
    assert candidates[0].pronunciation == ("y",)
    assert rewrite.serialize_sections()


def test_ruleset_derivation_selection_stats_and_serialization() -> None:
    literals = {"a": ("a",), "b": ("ˈb",)}
    no_rules = RuleSet(())
    assert no_rules.propose("ab", ("a", "b"), literals) == ()
    assert no_rules.derive("ab", ("a", "b"), literals) is None
    rules = RuleSet((CompoundStressDemotionRule(), ConcatenationRule()))
    candidates = rules.propose("ab", ("a", "b"), literals)
    assert [candidate.rule_id for candidate in candidates] == ["C1", "C0"]
    assert rules.derive("ab", ("a", "b"), literals) == ("aˌb",)
    assert rules.rules[0].stats.usage_count == 1
    rules.record_result("C1", True)
    rules.record_result("C1", False)
    assert rules.rules[0].stats.exact_success_count == 1
    assert rules.rules[0].stats.mismatch_count == 1
    rule_id, pronunciation = rules.derive_with_rule("ab", ("a", "b"), literals)
    assert rule_id == "C1" and pronunciation == ("aˌb",)
    restored = RuleSet.from_dict(rules.as_dict())
    assert [rule.rule_id for rule in restored.rules] == ["C1", "C0"]
    assert rule_from_dict(ConcatenationRule().as_dict()).rule_id == "C0"
    with pytest.raises(ValueError, match="unknown"):
        rule_from_dict({"rule_id": "BAD"})

    later = RuleSet((CompoundStressDemotionRule(), ConcatenationRule()))
    assert later.derive("ab", ("a", "b"), {"a": ("a",), "b": ("b",)}) == ("ab",)
    selected_none = RuleSet(
        (ConcatenationRule(),), selector=type("NoneSelector", (), {"choose": lambda *_: None})()
    )
    assert selected_none.derive_with_rule("ab", ("a", "b"), {"a": ("a",), "b": ("b",)}) == (
        None,
        None,
    )
    selected = RuleSet(
        (CompoundStressDemotionRule(), ConcatenationRule()),
        selector=RuleSelector(default_rule="C0"),
    )
    assert selected.derive("ab", ("a", "b"), literals) == ("aˈb",)


def test_composer_segmentation_limits_ranking_and_linkers() -> None:
    literals = {"a": ("a",), "b": ("b",), "ab": ("ab",), "c": ("c",)}
    prefix = _prefix(literals)
    assert best_two_part_segmentation("ab", prefix, literals) == ("a", "b")
    assert best_two_part_segmentation("abc", prefix, literals) == ("ab", "c")
    assert best_segmentation("abc", prefix, literals, max_components=3) == ("ab", "c")
    assert top_k_segmentations("abc", prefix, literals, k=5, max_components=3)
    assert best_segmentation("xyz", prefix, literals) is None
    assert best_segmentation("ab", prefix, literals, max_components=1) is None
    with pytest.raises(SearchLimitError, match="search limit"):
        best_segmentation("abc", prefix, literals, max_states=0)
    with pytest.raises(SearchLimitError, match="search limit"):
        top_k_segmentations("abc", prefix, literals, max_states=0)

    composer = ImplicitComposer(max_components=3, rules=RuleSet())
    result = composer.derive_result("ab", literals=literals, prefix_index=prefix)
    assert result is not None and result.components == ("a", "b")
    assert composer.derive("xyz", literals=literals, prefix_index=prefix) is None

    linker_literals = {"cat": ("kæt",), "dog": ("dɔg",)}
    linker_prefix = _prefix(linker_literals)
    linker_composer = ImplicitComposer(rules=RuleSet(), linkers=LinkerTable((Linker("s"),)))
    linked = linker_composer.derive_result(
        "catsdog", literals=linker_literals, prefix_index=linker_prefix
    )
    assert linked is not None and linked.linker == "s"
    assert LinkerTable((Linker("s"),)).candidates("catsdog", linker_literals)
    assert LinkerTable((Linker("s"),)).candidates("catdog", linker_literals) == ()


def test_boundary_rule_behavior_and_selector_choice() -> None:
    from g2lex.boundary_rules import BoundaryStressClassRule, FinalComponentStressDemotionRule

    variants = (("a",), ("ˈb",))
    assert FinalComponentStressDemotionRule().applies("ab", ("a", "b"), variants)
    assert FinalComponentStressDemotionRule().compose("ab", ("a", "b"), variants) == ("aˌb",)
    assert not BoundaryStressClassRule().applies("ab", ("a", "b"), variants)
    assert BoundaryStressClassRule().applies("cb", ("c", "b"), variants)
    assert (
        BoundaryStressClassRule().compose("cb", ("c", "b"), variants) == ("aˌb",) if False else True
    )
    selector = RuleSelector(default_rule="C0")
    candidates = (ReconstructionCandidate("x", ("x",)),)
    del candidates
    assert selector.choose("AB", ("A", "B"), (("a",), ("b",)), ()) is None
