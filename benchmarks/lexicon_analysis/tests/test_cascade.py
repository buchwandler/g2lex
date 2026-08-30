from __future__ import annotations

from benchmarks.lexicon_analysis.cascade import evaluate_cascade
from g2lex import LayeredLexicon, LexiconLayer


def test_cascade_uses_production_precedence_and_reports_metrics() -> None:
    layers = [
        LexiconLayer("user", {"one": ("u",), "conflict": ("u",), "user-only": ("u",)}, {}),
        LexiconLayer("domain", {"conflict": ("d",), "domain-only": ("d",)}, {}),
        LexiconLayer("base", {"conflict": ("b",), "base-only": ("b",)}, {}),
    ]
    reference = {
        "one": ("u",),
        "conflict": ("d",),
        "domain-only": ("d",),
        "base-only": ("b",),
        "missing": ("x",),
    }
    report = evaluate_cascade(
        LayeredLexicon(layers),
        ["one", "conflict", "user-only", "domain-only", "base-only", "missing"],
        reference=reference,
    )
    assert report["layers"] == ["user", "domain", "base"]
    assert report["total_evaluated_words"] == 6
    assert report["coverage"] == 5 / 6
    assert report["hits_by_source"] == {"base": 2, "domain": 2, "user": 3}
    assert report["incremental_hits_by_source"] == {"base": 1, "domain": 1, "user": 3}
    assert report["conflict_wins_by_source"] == {"user": 1}
    assert report["fallback_miss_count"] == 1
    assert report["selected_exact_match"] == 3
    assert report["oracle_any_layer_exact_match"] == 4
    assert report["incremental_exact_matches_by_source"] == {"base": 1, "domain": 1, "user": 1}
    assert report["incremental_errors_by_source"] == {"user": 1}
    assert (
        next(row for row in report["rows"] if row["word"] == "conflict")["selected_source"]
        == "user"
    )


def test_cascade_accepts_layers_directly_and_keeps_exact_values() -> None:
    layers = [
        LexiconLayer("first", {"word": "raw"}, {}),
        LexiconLayer("second", {"word": "other"}, {}),
    ]
    report = evaluate_cascade(layers)
    assert report["rows"][0]["selected_value"] == "raw"
    assert report["rows"][0]["hit_sources"] == ["first", "second"]
