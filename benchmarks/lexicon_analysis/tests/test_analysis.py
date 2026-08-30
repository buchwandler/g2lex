from __future__ import annotations

from pathlib import Path

from benchmarks.lexicon_analysis.analysis import (
    collision_groups,
    key_statistics,
    source_shape,
    source_summary,
)
from g2lex import SourceInfo, TaggedValue, TypedLexiconData
from g2lex.adapters.tsv import parse_tsv_bytes


def test_collision_groups_are_analysis_only_and_deterministic() -> None:
    words = ("Haus", "haus", "Straße", "STRASSE")
    assert collision_groups(words, str.lower) == {"haus": ("Haus", "haus")}
    assert collision_groups(words, str.casefold) == {
        "haus": ("Haus", "haus"),
        "strasse": ("STRASSE", "Straße"),
    }
    assert collision_groups(words, lambda value: value) == {}
    assert words == ("Haus", "haus", "Straße", "STRASSE")


def test_source_shape_preserves_rows_and_duplicate_variants() -> None:
    fixture = Path(__file__).parents[1] / "fixtures" / "variants-a.tsv"
    source = parse_tsv_bytes(fixture.read_bytes(), source_id="variants")
    assert source.entries["weg"] == ("vɛk", "veːk", "vɛk")
    assert source_shape(source) == {
        "physical_rows": 3,
        "logical_spellings": 1,
        "pronunciation_value_count": 3,
        "multi_variant_words": 1,
        "maximum_variant_count": 3,
        "duplicate_identical_rows": 1,
    }


def test_typed_values_are_traversed_without_flattening() -> None:
    value = TaggedValue((("DEFAULT", ("a", "b")), ("formal", "c")))
    source = TypedLexiconData(
        {"word": value},
        SourceInfo("typed", revision="r1", license="MIT", attribution="author"),
        physical_rows=2,
    )
    assert source_shape(source)["pronunciation_value_count"] == 3
    summary = source_summary(source)
    assert summary["provenance"]["revision"] == "r1"
    assert summary["provenance"]["license"] == "MIT"
    assert summary["provenance"]["attribution"] == "author"
    assert summary["keys"] == key_statistics(source)
