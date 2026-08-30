from __future__ import annotations

from benchmarks.lexicon_analysis.compare import (
    compare_sources,
    conflict_samples,
    cross_source_sharing,
    pairwise_sources,
)
from g2lex import SourceInfo, TaggedValue, TypedLexiconData


def _sources() -> tuple[TypedLexiconData, TypedLexiconData]:
    left = TypedLexiconData(
        {
            "same": ("a",),
            "different": ("left",),
            "shared": ("one", "two"),
            "left-only": ("l",),
            "Haus": ("h",),
            "tagged": TaggedValue((("DEFAULT", "x"),)),
        },
        SourceInfo("left", revision="l1", license="left-license"),
        physical_rows=7,
    )
    right = TypedLexiconData(
        {
            "same": ("a",),
            "different": ("right",),
            "shared": ("two", "three"),
            "right-only": ("r",),
            "haus": ("h",),
            "tagged": TaggedValue((("DEFAULT", "x"),)),
        },
        SourceInfo("right", revision="r1", license="right-license"),
        physical_rows=7,
    )
    return left, right


def test_pairwise_metrics_cover_spelling_values_variants_and_conflicts() -> None:
    left, right = _sources()
    report = compare_sources(left, right, conflict_limit=1)
    assert report["logical_entry_count_a"] == 6
    assert report["logical_entry_count_b"] == 6
    assert report["exact_spelling_intersection"] == 4
    assert report["exact_spelling_union"] == 8
    assert report["jaccard_overlap"] == 0.5
    assert report["lowercase_key_intersection"] == 5
    assert report["casefold_key_intersection"] == 5
    assert report["nfc_key_intersection"] == 4
    assert report["exact_typed_agreement"] == 2
    assert report["pronunciation_any_variant_agreement"] == 3
    assert report["shape_conflicts"] == 0
    assert report["value_conflicts"] == 1
    assert report["variant_agreement"] == {
        "same_ordered_tuple": 2,
        "same_unordered_variant_set": 0,
        "partial_variant_overlap": 1,
        "no_variant_overlap": 1,
    }
    assert report["conflicting_overlapping_entries"] == 2
    assert len(report["conflicts"]) == 1
    assert report["conflicts"][0]["word"] == "different"


def test_conflict_samples_are_sorted_and_bounded() -> None:
    left, right = _sources()
    assert [row["word"] for row in conflict_samples(left, right)] == ["different", "shared"]
    assert conflict_samples(left, right, limit=0) == []


def test_pairwise_and_sharing_keep_source_identity() -> None:
    left, right = _sources()
    pairs = pairwise_sources({"z-left": left, "a-right": right})
    assert [(row["source_a"], row["source_b"]) for row in pairs] == [("right", "left")]
    sharing = cross_source_sharing({"left": left, "right": right})
    assert sharing["identical_spelling_identical_typed_value"] == 2
    assert sharing["identical_spelling_shared_pronunciation_variant"] == 3
    assert sharing["identical_pronunciation_strings_used_by_multiple_sources"] == 4
    assert sharing["pairs"][0]["source_a"] == "left"
