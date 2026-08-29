from __future__ import annotations

from types import SimpleNamespace

import pytest

from g2lex.builder import BuildResult
from g2lex.model import CandidateMetrics, LexiconData
from g2lex.optimizer import _promotion_candidates, optimize_basis
from g2lex.verify import verify_candidate


def _fake_result(
    literals: tuple[str, ...], failures: list[dict[str, object]], count: int
) -> BuildResult:
    return BuildResult(
        SimpleNamespace(literals=literals, metadata={}),
        CandidateMetrics(5, count, 5 - count),
        failures,
    )


def test_promotion_candidates_filters_scores_and_is_deterministic() -> None:
    source = LexiconData.from_pairs(*[(word, word) for word in ("a", "b", "c", "ab", "abc")])
    result = _fake_result(
        ("a", "ab"),
        [
            {"word": "abc", "reason": "pronunciation-mismatch"},
            {"word": "abc", "reason": "no-composition"},
            {"word": "b", "reason": "no-composition"},
            {"word": "abc", "reason": "search-limit"},
        ],
        2,
    )
    assert _promotion_candidates(source, result) == ("b", "abc", "c")
    assert _promotion_candidates(source, result, limit=2) == ("b", "abc")


def test_optimizer_state_machine_promotes_and_records_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = LexiconData.from_pairs(
        ("a", "x"), ("b", "y"), ("ab", "xy"), ("c", "z"), ("abc", "xyz")
    )
    calls: list[frozenset[str]] = []

    def fake_build(_source: LexiconData, **kwargs: object) -> BuildResult:
        forced = frozenset(kwargs["forced_literals"])  # type: ignore[arg-type]
        calls.append(forced)
        if not forced:
            return _fake_result(
                ("a", "ab"),
                [{"word": "ab", "reason": "no-composition"}],
                2,
            )
        if forced == {"b"}:
            return _fake_result(
                ("a",),
                [{"word": "ab", "reason": "no-composition"}],
                1,
            )
        return _fake_result(("a", "ab"), [], 2)

    monkeypatch.setattr("g2lex.optimizer.build_implicit_lexicon", fake_build)
    result = optimize_basis(source, target_literals=1, max_passes=3)
    assert [item.promoted_word for item in result.passes] == ["b"]
    assert result.reached_target
    assert result.build.asset.metadata == {
        "optimizer": "utility",
        "optimization_pass_count": 1,
        "promoted_word_count": 1,
        "words_removed_due_to_promotions": 2,
        "net_literal_reduction": 1,
        "optimizer_candidates_evaluated": 1,
        "optimizer_full_rebuilds": 2,
    }
    assert calls == [frozenset(), frozenset({"b"})]


def test_optimizer_stops_for_target_empty_candidates_and_max_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = LexiconData.from_pairs(("a", "x"), ("b", "y"), ("ab", "xy"))
    calls = 0

    def fake_build(_source: LexiconData, **kwargs: object) -> BuildResult:
        nonlocal calls
        calls += 1
        forced = set(kwargs["forced_literals"])  # type: ignore[arg-type]
        return _fake_result(("a", "b") if not forced else ("a",), [], 2 if not forced else 1)

    monkeypatch.setattr("g2lex.optimizer.build_implicit_lexicon", fake_build)
    reached = optimize_basis(source, target_literals=3)
    assert reached.reached_target and calls == 1 and reached.passes == []

    calls = 0
    empty = optimize_basis(source, target_literals=0, max_passes=0)
    assert not empty.reached_target and empty.passes == [] and calls == 1

    # No positive reduction means that a candidate trial is not selected.
    def no_reduction(_source: LexiconData, **kwargs: object) -> BuildResult:
        return _fake_result(("a", "ab"), [{"word": "ab", "reason": "no-composition"}], 2)

    monkeypatch.setattr("g2lex.optimizer.build_implicit_lexicon", no_reduction)
    stalled = optimize_basis(source, target_literals=0)
    assert stalled.passes == [] and not stalled.reached_target


def test_optimizer_real_build_remains_lossless_and_repeatable() -> None:
    source = LexiconData.from_pairs(
        ("a", "x"), ("b", "y"), ("ab", "xy"), ("c", "z"), ("abc", "xyz")
    )
    first = optimize_basis(source, target_literals=0, max_passes=2)
    second = optimize_basis(source, target_literals=0, max_passes=2)
    assert first.passes == second.passes
    assert first.build.asset.metadata == second.build.asset.metadata
    assert verify_candidate(first.build.asset, source)["lossless"]
