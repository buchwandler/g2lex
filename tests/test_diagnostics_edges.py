from __future__ import annotations

import json
from pathlib import Path

from g2lex.builder import build_implicit_lexicon
from g2lex.diagnostics import (
    _boundary_family,
    analyze_failures,
    linker_diagnostics,
    write_diagnostics,
)
from g2lex.linkers import Linker, LinkerTable
from g2lex.model import LexiconData


def test_boundary_family_classification_matrix() -> None:
    components = ("a", "b")
    variants = (("a",), ("b",))
    assert _boundary_family("x", "y", None, None, 2)["family"] == "non-local mismatch"
    assert (
        _boundary_family("aˈb", "aˌb", components, variants, 2)["family"]
        == "primary stress → secondary stress"
    )
    assert _boundary_family("ab", "aˈb", components, variants, 2)["family"] == "insert stress"
    assert _boundary_family("aˈb", "ab", components, variants, 2)["family"] == "delete stress"
    assert (
        _boundary_family("ab", "aXYZb", components, variants, 2)["family"]
        == "other boundary-local replacement"
    )
    assert (
        _boundary_family("axb", "ayb", components, variants, 2)["family"]
        == "local vowel/consonant alternation"
    )
    equal = _boundary_family("same", "same", components, variants, 2)
    assert equal["template"] == "equal"


def test_analyze_failures_and_linker_diagnostics() -> None:
    source = LexiconData.from_pairs(("a", "x"), ("b", "y"), ("ab", "wrong"))
    asset = build_implicit_lexicon(source, forced_literals=("ab",), linkers=None).asset
    result = analyze_failures(
        source,
        asset,
        failures=[
            {
                "word": "ab",
                "reason": "pronunciation-mismatch",
                "candidate": ["xy"],
                "candidate_components": ("a", "b"),
                "candidate_rule": "C0",
            }
        ],
        top_k=2,
    )
    assert result["pronunciation_mismatch_count"] == 1
    assert result["retained_groups"]["forced-literal"] == 2
    assert result["failure_details"][0]["top_k_exact_rank"] is None
    assert "not_exact_in_top_k" in result["top_k_segmentation_summary"]

    no_linkers = linker_diagnostics(source, asset)
    assert no_linkers["per_linker"] == {}

    linker_source = LexiconData.from_pairs(("cat", "kæt"), ("dog", "dɔg"), ("catsdog", "kætdɔg"))
    linker_asset = build_implicit_lexicon(linker_source, linkers=LinkerTable((Linker("s"),))).asset
    linker_result = linker_diagnostics(linker_source, linker_asset)
    assert linker_result["words_newly_segmentable_due_to_linkers"] == 1
    assert linker_result["words_newly_exact_due_to_linkers"] == 1
    assert linker_result["linker_rule_bytes"] > 0


def test_diagnostic_artifacts_are_stable_and_parseable(tmp_path: Path) -> None:
    result = {
        "failure_family_summary": {"counts": {"x": 1}},
        "alternate_rule_summary": {"selected_rule_exact": 1},
        "linker_summary": {"per_linker": {}},
        "top_k_segmentation_summary": {"k": 2},
        "boundary_patterns": [{"support_count": 1, "edit_template": "x"}],
        "failure_details": [{"word": "a", "selected_rule": "C0"}],
    }
    write_diagnostics(tmp_path, result)
    expected = {
        "failure_family_summary.json",
        "alternate_rule_summary.json",
        "linker_summary.json",
        "top_k_segmentation_summary.json",
        "top_100_boundary_patterns.tsv",
        "failure_families.tsv",
    }
    assert {path.name for path in tmp_path.iterdir()} == expected
    for name in expected:
        assert (tmp_path / name).read_text(encoding="utf-8")
    assert (
        json.loads((tmp_path / "failure_family_summary.json").read_text())
        == result["failure_family_summary"]
    )
    assert (
        (tmp_path / "top_100_boundary_patterns.tsv")
        .read_text()
        .splitlines()[0]
        .startswith("support_count\t")
    )
    first = (tmp_path / "failure_families.tsv").read_bytes()
    write_diagnostics(tmp_path, result)
    assert (tmp_path / "failure_families.tsv").read_bytes() == first
