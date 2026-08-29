"""Coverage for the public reduction orchestration API."""

from __future__ import annotations

from pathlib import Path

import pytest

from g2lex.linkers import german_linker_table
from g2lex.model import LexiconData
from g2lex.reduce import ReductionConfig, reduce_file, reduce_lexicon
from g2lex.rules import default_rules
from g2lex.verify import verify_candidate


def _source() -> LexiconData:
    return LexiconData.from_pairs(
        ("a", "x"),
        ("b", "y"),
        ("ab", "xy"),
        ("c", "z"),
        ("abc", "xyz"),
    )


@pytest.mark.parametrize("optimizer", ("greedy", "utility"))
def test_reduce_lexicon_supports_both_optimizers(optimizer: str) -> None:
    result = reduce_lexicon(
        _source(), config=ReductionConfig(optimizer=optimizer, target_literals=0)
    )

    assert result.asset.metadata["target_literal_word_count"] == 0
    assert verify_candidate(result.asset, _source())["lossless"]


def test_reduce_lexicon_rejects_unknown_optimizer() -> None:
    with pytest.raises(ValueError, match="unknown optimizer"):
        reduce_lexicon(_source(), config=ReductionConfig(optimizer="invalid"))


def test_reduce_file_writes_output_and_accepts_custom_settings(tmp_path: Path) -> None:
    source = tmp_path / "source.tsv"
    source.write_text("a\tx\nb\ty\nab\txy\n", encoding="utf-8")
    output = tmp_path / "reduced.lxc"

    result = reduce_file(
        source,
        output,
        input_format="tsv",
        config=ReductionConfig(
            optimizer="greedy",
            recursive_components=True,
            max_recursive_depth=2,
            max_components=2,
            max_states=128,
            target_literals=2,
            max_passes=1,
        ),
        rules=default_rules(False),
        linkers=german_linker_table(max_candidates=4),
    )

    assert output.exists()
    assert result.asset.metadata["target_literal_word_count"] == 2
    assert result.asset.composer.recursive_components is True
    assert result.asset.composer.max_recursive_depth == 2
