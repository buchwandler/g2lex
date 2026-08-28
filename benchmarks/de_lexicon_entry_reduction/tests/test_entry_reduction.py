from __future__ import annotations
import json
from pathlib import Path
import pytest
from lexcompact import LexiconData
from lexcompact.asset import asset_members, dumps, load, loads, save
from lexcompact.audit import audit_runtime_representation
from lexcompact.builder import build_implicit_lexicon
from lexcompact.composer import ImplicitComposer, SearchLimitError, best_segmentation
from lexcompact.linkers import german_linker_table
from lexcompact.membership import MembershipIndex
from lexcompact.model import LiteralLexicon
from lexcompact.optimizer import optimize_basis
from lexcompact.prefix_index import LiteralPrefixIndex
from lexcompact.profiles.german import BoundaryStressClassRule, FinalComponentStressDemotionRule, german_rules
from lexcompact.reports import summary_dict
from lexcompact.rules import default_rules
from lexcompact.selector import Candidate, RuleSelector, SelectorPredicate, extract_features, train_selector
from lexcompact.segmentation import SegmentationScorer
from lexcompact.verify import adversarial_misses, verify_candidate


def make_source(*pairs: tuple[str, str]) -> LexiconData:
    return LexiconData.from_pairs(*pairs)


def test_motivating_sum_rule_and_unknown_recombination() -> None:
    source=make_source(("1","a"),("2","b"),("12","ab")); result=build_implicit_lexicon(source); candidate=result.asset
    assert result.metrics.baseline_word_count==3 and result.metrics.literal_word_count==2 and result.metrics.generated_word_count==1
    assert candidate.per_generated_word_recipe_count==0; assert candidate.lookup_all("12")== ("ab",); assert candidate.is_known("12")
    assert candidate.lookup_all("21")==(); assert not candidate.is_known("21"); assert "12" not in candidate.literals; assert not hasattr(candidate,"derived")


def test_runtime_composer_has_no_oracle_and_keeps_ambiguous_word_literal() -> None:
    source=make_source(("A","a"),("C","c"),("AB","x"),("BC","bc"),("ABC","abc")); result=build_implicit_lexicon(source)
    assert "ABC" in result.asset.literals; assert result.asset.lookup_all("ABC")== ("abc",)
    assert result.asset.composer.derive("ABC",literals=result.asset.literals,prefix_index=result.asset.literal_index)==("xc",)


def test_variant_order_is_exact() -> None:
    source=make_source(("A","a1"),("A","a2"),("B","b1"),("B","b2"),("AB","a1b1")); result=build_implicit_lexicon(source)
    assert result.asset.lookup_all("AB")== ("a1b1",) and "AB" in result.asset.literals
    literals=LiteralLexicon({"A":("a1","a2"),"B":("b1","b2")}); composer=ImplicitComposer()
    assert composer.derive("AB",literals=literals,prefix_index=LiteralPrefixIndex.from_literals(literals)) == ("a1b1","a1b2","a2b1","a2b2")


def test_stress_rule_is_shared_and_oracle_free() -> None:
    source=make_source(("Haus","hˈaʊs"),("tür","tˈyːɐ"),("Haustür","hˈaʊstˌyːɐ"))
    concat=build_implicit_lexicon(source,rules=default_rules()); compound=build_implicit_lexicon(source,rules=german_rules())
    assert "Haustür" in concat.asset.literals; assert "Haustür" not in compound.asset.literals; assert compound.asset.lookup_all("Haustür")== ("hˈaʊstˌyːɐ",)


def test_deterministic_segmentation_and_state_limit() -> None:
    literals=LiteralLexicon({"a":("a",),"ab":("ab",),"bc":("bc",),"c":("c",)}); index=LiteralPrefixIndex.from_literals(literals)
    assert best_segmentation("abc",index,literals,max_components=3)==("ab","c")
    with pytest.raises(SearchLimitError): best_segmentation("abc",index,literals,max_components=4,max_states=1)


def test_membership_exact_and_deterministic() -> None:
    words=("Haus","Haustür","Tür"); membership=MembershipIndex.from_words(words); assert membership.iter_words()==tuple(sorted(words))
    assert all(membership.contains(w) for w in words); assert not any(membership.contains(w) for w in adversarial_misses(words)); assert membership.serialize()==MembershipIndex.from_words(words).serialize()


def test_serialization_round_trip_has_no_derived_table(tmp_path: Path) -> None:
    result=build_implicit_lexicon(make_source(("1","a"),("2","b"),("12","ab"))); data=dumps(result.asset)
    assert b"derived" not in data; reloaded=loads(data); assert reloaded.lookup_all("12")== ("ab",); assert reloaded.is_known("12") and not reloaded.is_known("21")
    save(tmp_path/"candidate.lxc",result.asset); assert load(tmp_path/"candidate.lxc").lookup_all("12")== ("ab",); assert "derived.json" not in asset_members(result.asset)


def test_deterministic_build_and_runtime_audit() -> None:
    source=make_source(("1","a"),("2","b"),("12","ab")); first=build_implicit_lexicon(source); second=build_implicit_lexicon(source)
    assert first.metrics==second.metrics; assert tuple(first.asset.literals)==tuple(second.asset.literals); assert dumps(first.asset)==dumps(second.asset)
    assert audit_runtime_representation(first.asset)["per_generated_word_recipe_count"]==0


def test_optimizer_and_verification_metrics() -> None:
    source=make_source(("1","a"),("2","b"),("12","ab")); optimized=optimize_basis(source,max_passes=2); verification=verify_candidate(optimized.build.asset,source,miss_words=("21",)); summary=summary_dict(optimized.build,verification=verification)
    assert optimized.build.metrics.literal_word_count==2; assert summary["entry_reduction_count"]==1; assert verification["words_checked"]==3 and verification["lossless"]


def test_selector_chooses_candidates_without_expected_ipa() -> None:
    variants=(("hˈaʊs",),("tˈyːɐ",)); features=extract_features("Haustür",("Haus","tür"),variants); selector=RuleSelector((SelectorPredicate("component_count","2","C0",100),),"C1")
    selected=selector.select(features,(Candidate("C1",("hˈaʊstˌyːɐ",)),Candidate("C0",("hˈaʊstˈyːɐ",))))
    assert selected and selected.rule_id=="C0"; assert "expected" not in selector.as_dict(); assert selector.serialized_bytes<=selector.max_serialized_bytes


def test_selector_round_trip_and_training_are_deterministic() -> None:
    variants=(("aˈ",),("bˈ",)); features=extract_features("ab",("a","b"),variants)
    first=train_selector(({"features":features,"target_rule":"C0"} for _ in range(100)),min_support=10); second=train_selector(({"features":features,"target_rule":"C0"} for _ in range(100)),min_support=10)
    assert first.as_dict()==second.as_dict(); assert RuleSelector.from_dict(first.as_dict())==first; assert all("ab" not in str(v) for v in first.as_dict().values())


def test_boundary_rules_are_shared_and_deterministic() -> None:
    variants=(("hˈaʊs",),("tˈyːɐ",)); final=FinalComponentStressDemotionRule(); assert final.applies("Haustür",("Haus","tür"),variants)
    assert final.compose("Haustür",("Haus","tür"),variants)==("hˈaʊstˌyːɐ",); assert BoundaryStressClassRule().applies("Haustür",("Haus","tür"),variants)


def test_linker_is_shared_and_membership_still_gates(tmp_path: Path) -> None:
    source=make_source(("Arbeit","a"),("zeit","z"),("Arbeitszeit","az")); result=build_implicit_lexicon(source,linkers=german_linker_table())
    assert result.metrics.generated_word_count==1; assert result.asset.lookup_all("Arbeitszeit")== ("az",); assert not result.asset.is_known("Arbeitszeitx")
    save(tmp_path/"candidate.lxc",result.asset); assert load(tmp_path/"candidate.lxc").lookup_all("Arbeitszeit")== ("az",); assert not hasattr(result.asset,"derived")


def test_recursive_generated_constituents_are_ephemeral() -> None:
    source=make_source(("A","a"),("B","b"),("C","c"),("AB","ab"),("ABC","abc"))
    result=build_implicit_lexicon(source,recursive_components=True,max_components=2)
    assert result.metrics.literal_word_count==3
    assert result.metrics.generated_word_count==2
    assert result.asset.lookup_all("AB")==("ab",)
    assert result.asset.lookup_all("ABC")==("abc",)
    assert not hasattr(result.asset,"derived")
    assert result.asset.per_generated_word_recipe_count==0


def test_recursive_and_segmentation_scorer_round_trip(tmp_path: Path) -> None:
    source=make_source(("A","a"),("B","b"),("C","c"),("AB","ab"),("ABC","abc"))
    result=build_implicit_lexicon(
        source,
        recursive_components=True,
        max_components=2,
        segmentation_scorer=SegmentationScorer(),
    )
    path=tmp_path/"recursive.lxc"
    save(path,result.asset)
    reloaded=load(path)
    assert reloaded.composer.recursive_components is True
    assert reloaded.composer.segmentation_scorer is not None
    assert reloaded.lookup_all("ABC")==("abc",)
    assert verify_candidate(reloaded,source)["lossless"]
