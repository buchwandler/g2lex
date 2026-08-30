from __future__ import annotations

import json
from pathlib import Path

from benchmarks.lexicon_analysis.reporting import jsonable, write_run


def test_jsonable_preserves_typed_value_shape() -> None:
    from g2lex import WORD_ONLY, TaggedValue

    assert jsonable(WORD_ONLY) == "WORD_ONLY"
    assert jsonable(TaggedValue((("DEFAULT", ("a", "b")),))) == {"DEFAULT": ["a", "b"]}


def test_write_run_emits_all_deterministic_tables(tmp_path: Path) -> None:
    summary = {
        "sources": [
            {
                "source": "a",
                "keys": {"lower_collisions": {"x": ("X", "x")}},
                "unicode": {"nfc_collision_groups": 1},
            }
        ],
        "pairs": [
            {
                "source_a": "a",
                "source_b": "b",
                "conflicts": [{"word": "x", "left": ("a",), "right": ("b",)}],
            }
        ],
        "layers": {"rows": [{"word": "x", "selected_source": "a", "selected_value": ("a",)}]},
    }
    write_run(tmp_path, summary)
    assert {path.name for path in tmp_path.iterdir()} == {
        "summary.json",
        "sources.tsv",
        "pairs.tsv",
        "conflicts.tsv",
        "collisions.tsv",
        "unicode.tsv",
        "layers.tsv",
    }
    first = (tmp_path / "summary.json").read_text()
    write_run(tmp_path, summary)
    assert (tmp_path / "summary.json").read_text() == first
    assert json.loads(first)["pairs"][0]["conflicts"][0]["left"] == ["a"]
